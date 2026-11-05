"""Append references to stored official paragraphs; no score publication."""
from .postgres import ScorePublicationError
from ..ingestion.uk_warning_areas import checked_references, EXTRACTOR_VERSION


def store_warning_excerpts(conn, version_id, raw_payload):
    from sqlalchemy import text
    stored={r['paragraph_index']:{'heading':r['heading'],'text':r['body']} for r in conn.execute(text('''
        SELECT paragraph_index,heading,body FROM advisory.paragraphs
        WHERE version_id=:version AND section_slug='warnings-and-insurance'
    '''),{'version':version_id}).mappings()}
    try:
        references=checked_references(raw_payload,stored)
    except ValueError as error:
        raise ScorePublicationError('UK warning extraction does not match stored source paragraphs.') from error
    # A versioned extractor cannot silently revise its prior references.
    existing={r['paragraph_index']:r['warning_heading'] for r in conn.execute(text('''
            SELECT paragraph_index,warning_heading FROM advisory.warning_excerpts
            WHERE version_id=:version AND extractor_version=:extractor
    '''),{'version':version_id,'extractor':EXTRACTOR_VERSION}).mappings()}
    expected={r['paragraph_index']:r['warning_heading'] for r in references}
    if existing and existing!=expected:
        raise ScorePublicationError('Warning extraction changed without an extractor-version update.')
    if references:
        if not existing:
            conn.execute(text('''INSERT INTO advisory.warning_excerpts
                (version_id,extractor_version,section_slug,paragraph_index,warning_heading)
                VALUES (:version,:extractor,:section_slug,:paragraph_index,:warning_heading)'''),
                [{'version':version_id,'extractor':EXTRACTOR_VERSION,**r} for r in references])
    return len(references)
