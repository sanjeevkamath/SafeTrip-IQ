"""Validate the captured legacy release before importing it into local Postgres."""
import csv
import hashlib
import json
import re
from pathlib import Path

from safetrip.scoring.legacy import legacy_safety_score

TABLES = ('countries', 'culture', 'scores', 'bert_scores', 'clustering', 'travel_advisories')
MANIFEST_SHA256 = '10b21e8d74f7eb43d1a6b4568da6569b737100f85d6f01dedd0993be833ac4e7'
CLUSTERS_SHA256 = 'e9e960d17a29de0f65eb80cf7ccc9557d59dc128727673a8a9b5ab8c85a3c998'
RISK_MAPPING = {1:0, 0:1, 3:2, 2:3, 4:4}


def load_baseline(directory, clusters_path):
    directory = Path(directory)
    manifest_bytes = (directory / 'manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Snapshot is not the reviewed legacy release.')
    manifest = json.loads(manifest_bytes)
    tables = {}
    for table in TABLES:
        content = (directory / f'{table}.json').read_bytes()
        if hashlib.sha256(content).hexdigest() != manifest['tables'][table]['sha256']:
            raise ValueError('Snapshot table checksum mismatch.')
        tables[table] = json.loads(content)
        if len(tables[table]) != manifest['tables'][table]['rows']:
            raise ValueError('Snapshot row count mismatch.')
    cluster_bytes = Path(clusters_path).read_bytes()
    if hashlib.sha256(cluster_bytes).hexdigest() != CLUSTERS_SHA256:
        raise ValueError('Frozen cluster release checksum mismatch.')
    raw = {row['iso3']:int(row['cluster']) for row in csv.DictReader(cluster_bytes.decode().splitlines())}
    report = validate_tables(tables, raw)
    # Kosovo is explicitly present in the source feed but absent from its catalog.
    # Preserve its source name; do not invent culture, model output, or ISO2 data.
    advisory = next(row for row in tables['travel_advisories'] if row['iso3'] == 'XKX')
    tables['countries'].append({'iso3':'XKX', 'name':advisory['country_name'],
                               'iso2':None, 'continent':None, 'flag_url':None})
    metadata = {'source_kind':'legacy_snapshot', 'captured_at':manifest['captured_at_utc'],
                'snapshot_manifest_sha256':MANIFEST_SHA256, 'clustering_release_sha256':CLUSTERS_SHA256,
                'cluster_risk_mapping':RISK_MAPPING, 'model_version':None,
                'catalog_additions':[{'iso3':'XKX','source':'captured advisory country_name'}]}
    return tables, metadata, report


def validate_tables(tables, raw_clusters):
    indexed = {}
    for table in TABLES:
        rows = tables[table]
        if any(not isinstance(row.get('iso3'), str) or not re.fullmatch('[A-Z]{3}', row['iso3']) for row in rows):
            raise ValueError('Invalid ISO3 in snapshot.')
        indexed[table] = {row['iso3']:row for row in rows}
        if len(indexed[table]) != len(rows):
            raise ValueError('Duplicate snapshot identifier.')
    countries = set(indexed['countries'])
    for table in TABLES:
        allowed = countries | ({'XKX'} if table == 'travel_advisories' else set())
        if set(indexed[table]) - allowed:
            raise ValueError('Unresolved snapshot country reference.')
    if set(raw_clusters) != set(indexed['clustering']):
        raise ValueError('Cluster release country set mismatch.')
    for iso3, row in indexed['clustering'].items():
        if row['clustering_score'] != RISK_MAPPING[raw_clusters[iso3]]:
            raise ValueError('Stored cluster tier disagrees with frozen raw-ID mapping.')
    covered = set(indexed['bert_scores']) | set(indexed['clustering'])
    if set(indexed['scores']) != covered:
        raise ValueError('Stored score coverage differs from its components.')
    coverage = dict(both=0, bert_only=0, clustering_only=0, neither=0)
    for iso3 in countries | set(indexed['travel_advisories']):
        bert = indexed['bert_scores'].get(iso3, {}).get('bert_score')
        cluster = indexed['clustering'].get(iso3, {}).get('clustering_score')
        value = legacy_safety_score(bert, cluster)
        if iso3 in indexed['scores']:
            saved = indexed['scores'][iso3]
            if (saved['bert_score'],saved['clustering_score'],saved['safe_trip_score']) != (bert,cluster,value):
                raise ValueError('Captured final score does not match its components.')
        kind = 'both' if bert is not None and cluster is not None else 'bert_only' if bert is not None else 'clustering_only' if cluster is not None else 'neither'
        coverage[kind] += 1
    return {'captured_rows':{t:len(tables[t]) for t in TABLES},
            'imported_countries':len(countries | set(indexed['travel_advisories'])),
            'verified_cluster_rows':len(raw_clusters), 'matched_scores':len(indexed['scores']), 'coverage':coverage}
