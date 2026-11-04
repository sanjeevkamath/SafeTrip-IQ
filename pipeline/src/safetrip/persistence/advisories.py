"""Atomic append-only V2 ingestion using the existing writer and run ledger."""
import hashlib
from uuid import NAMESPACE_URL, uuid4, uuid5

from .history import encode
from .postgres import PostgresPublisher, ScorePublicationError


def semantic_hash(row):
    fields = ('source_url', 'country_name', 'source_public_updated_at', 'source_updated_at',
              'source_reviewed_at', 'us_level', 'uk_alert_status', 'coverage', 'sections')
    return hashlib.sha256(encode({k: row[k] for k in fields}).encode()).hexdigest()


def ingest_capture(publisher, bundle):
    """Keep raw capture on failure; commit all normalized documents or none."""
    from sqlalchemy import text
    from safetrip.ingestion.multisource import normalize_bundle, preview
    if not isinstance(publisher, PostgresPublisher):
        raise ValueError('V2 ingestion requires the restricted PostgreSQL writer.')
    publisher.start_run('ingest-advisories')
    try:
        publisher.retain_raw(encode(bundle).encode())
        rows = normalize_bundle(bundle)
        report = preview(rows, requested=bundle.get('iso3'))
        publisher.history.record_input(report, {'source_kind': 'us_uk_capture', 'parser_version': report['parser_version'],
                                                'public_scores_changed': False})
        counts = {'documents': len(rows), 'new_documents': 0, 'new_versions': 0,
                  'reused_versions': 0, 'observations': 0, 'review_required': report['review_required']}
        with publisher.engine.begin() as conn:
            publisher._lock(conn)
            countries = set(conn.execute(text('SELECT iso3 FROM public.countries')).scalars())
            if any(c['iso3'] is not None and c['iso3'] not in countries for r in rows for c in r['coverage']):
                raise ScorePublicationError('Country catalogue is incomplete; seed countries before V2 ingestion.')
            for row in rows:
                identity = {'source': row['source'], 'source_key': row['source_key']}
                new_id = uuid5(NAMESPACE_URL, encode([row['source'], row['source_key']]))
                inserted = conn.execute(text('''INSERT INTO advisory.documents(document_id,source,source_key)
                    VALUES (:id,:source,:source_key) ON CONFLICT (source,source_key) DO NOTHING RETURNING document_id'''),
                    {'id': new_id, **identity}).scalar_one_or_none()
                counts['new_documents'] += inserted is not None
                doc_id = inserted or conn.execute(text('''SELECT document_id FROM advisory.documents
                    WHERE source=:source AND source_key=:source_key'''), identity).scalar_one()
                version_id = uuid5(doc_id, encode([row['parser_version'], row['content_sha256']]))
                fingerprint = semantic_hash(row)
                metadata = {**row['metadata'], 'country_name': row['country_name'], 'normalization_sha256': fingerprint}
                params = {**row, 'version_id': version_id, 'document_id': doc_id, 'metadata': encode(metadata)}
                inserted_version = conn.execute(text('''INSERT INTO advisory.versions
                    (version_id,document_id,source,parser_version,content_sha256,raw_payload,source_url,
                     source_public_updated_at,source_updated_at,source_reviewed_at,us_level,uk_alert_status,metadata)
                    VALUES (:version_id,:document_id,:source,:parser_version,:content_sha256,:raw_payload,:source_url,
                     :source_public_updated_at,:source_updated_at,:source_reviewed_at,:us_level,:uk_alert_status,CAST(:metadata AS jsonb))
                    ON CONFLICT (document_id,content_sha256,parser_version) DO NOTHING RETURNING version_id'''), params).scalar_one_or_none()
                if inserted_version is None:
                    previous = conn.execute(text('''SELECT version_id,metadata FROM advisory.versions
                        WHERE document_id=:document_id AND content_sha256=:content_sha256 AND parser_version=:parser_version'''), params).mappings().one()
                    version_id = previous['version_id']
                    if previous['metadata'].get('normalization_sha256') != fingerprint:
                        raise ScorePublicationError('Normalization changed without a parser-version update; refusing stale reuse.')
                    counts['reused_versions'] += 1
                else:
                    counts['new_versions'] += 1
                    for target in row['coverage']:
                        conn.execute(text('''INSERT INTO advisory.coverage(coverage_id,version_id,iso3,scope,region_label)
                            VALUES (:id,:version,:iso3,:scope,:region_label)'''),
                            {'id': uuid4(), 'version': version_id, **target})
                    for section in row['sections']:
                        for index, paragraph in enumerate(section['paragraphs']):
                            conn.execute(text('''INSERT INTO advisory.paragraphs
                                (version_id,section_slug,paragraph_index,section_title,heading,body)
                                VALUES (:version,:slug,:idx,:title,:heading,:body)'''),
                                {'version': version_id, 'slug': section['slug'], 'idx': index,
                                 'title': section['title'], 'heading': paragraph['heading'], 'body': paragraph['text']})
                conn.execute(text('''INSERT INTO advisory.observations(run_id,document_id,version_id,fetched_at)
                    VALUES (:run,:doc,:version,:fetched)'''),
                    {'run': publisher.history.active, 'doc': doc_id, 'version': version_id, 'fetched': row['fetched_at']})
                counts['observations'] += 1
            publisher.history.succeeded(conn, coverage=counts, published_rows=0)
        publisher.history.committed()
        return {**report, 'database_written': True, 'run_id': str(publisher.last_run_id), 'storage': counts}
    except BaseException as error:
        publisher.fail_run(error)
        raise
