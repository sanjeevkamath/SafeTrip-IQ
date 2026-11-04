"""Source capture and normalization for V2; never loads a model or writes scores."""
import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from .advisories import FEED_URL
from .countries import resolve_iso3
from .uk_advisories import destination, normalize_uk, paragraphs

FORMAT = 'safetrip-advisory-capture-v1'
PARSER_VERSION = 'us-uk-ingestion-v2'
US_COMPOUND_CANDIDATES = {
    'french west indies': ['GLP', 'MTQ', 'MAF', 'BLM'],
    'mainland china, hong kong & macau - see summaries': ['CHN', 'HKG', 'MAC'],
    'kingdom of denmark': ['DNK', 'GRL', 'FRO'],
}
UK_BASE = 'https://www.gov.uk/api/content'
UK_INDEX = UK_BASE + '/foreign-travel-advice'


class AdvisoryValidationError(ValueError):
    """Fixed, credential-free validation messages safe to show in the CLI."""


def timestamp(value, *, optional=False):
    if not value and optional:
        return None
    if not isinstance(value, str):
        raise AdvisoryValidationError('Missing source timestamp.')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            result = datetime.strptime(value, '%a, %d %b %Y').replace(tzinfo=timezone.utc)
    if result.tzinfo is None:
        raise AdvisoryValidationError('Timestamp requires a timezone.')
    return result.astimezone(timezone.utc).isoformat()


def official_url(value, source):
    if not isinstance(value, str):
        raise AdvisoryValidationError('Missing source URL.')
    parsed = urlsplit(value)
    hosts = {'us_state': {'travel.state.gov'}, 'uk_fcdo': {'www.gov.uk'}, 'uk_index': {'www.gov.uk'}}
    if (parsed.scheme != 'https' or parsed.hostname not in hosts[source] or parsed.username
            or parsed.password or parsed.port not in {None, 443} or parsed.fragment or parsed.query):
        raise AdvisoryValidationError('Unexpected official source URL.')
    return value


def envelope(source, url, body, fetched_at):
    return {'source': source, 'url': official_url(url, source), 'fetched_at': timestamp(fetched_at),
            'sha256': hashlib.sha256(body).hexdigest(), 'body_base64': base64.b64encode(body).decode('ascii')}


def decode_capture(item):
    official_url(item['url'], item['source'])
    timestamp(item['fetched_at'])
    body = base64.b64decode(item['body_base64'], validate=True)
    if not body or hashlib.sha256(body).hexdigest() != item['sha256']:
        raise AdvisoryValidationError('Captured bytes differ from their checksum.')
    return body


def selection(value):
    if value is None:
        return None
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not re.fullmatch('[A-Z]{3}', x) for x in value):
        raise AdvisoryValidationError('Select explicit ISO3 codes or all destinations.')
    return set(value)


def uk_targets(index, selected):
    if index.get('document_type') != 'travel_advice_index':
        raise AdvisoryValidationError('Expected the UK destination index.')
    children = index['links']['children']
    if not children:
        raise AdvisoryValidationError('Empty UK destination index.')
    targets = {}
    for child in children:
        if child.get('withdrawn'):
            continue
        country = child['details']['country']
        try:
            identity = destination(country)
        except ValueError:
            if selected is not None:
                raise AdvisoryValidationError('Unmapped UK identity prevents reliable subset selection.')
            identity = {'covered_iso3': [], 'mapping_review_required': True}
        if selected is not None and not selected.intersection(identity['covered_iso3']):
            continue
        path = child['base_path']
        if not re.fullmatch(r'/foreign-travel-advice/[a-z0-9-]+', path):
            raise AdvisoryValidationError('Unexpected UK destination path.')
        url = UK_BASE + path
        if url in targets:
            raise AdvisoryValidationError('Duplicate UK destination path.')
        targets[url] = {'source_key': child['content_id'], **identity}
    return targets


def coverage(identity, name):
    if identity['mapping_review_required']:
        return [{'iso3': None, 'scope': 'unresolved', 'region_label': name}]
    return [{'iso3': identity['iso3'], 'scope': 'whole_country', 'region_label': None}]


def us_documents(body, fetched_at, selected):
    channel = ET.fromstring(body).find('channel')
    if channel is None:
        raise AdvisoryValidationError('US feed lacks a channel.')
    rows = []
    valid_items = 0
    for item in channel.findall('item'):
        title = item.findtext('title', '').strip()
        match = re.fullmatch(r'(.+?)\s+[–-]\s+Level\s*([1-4])(?:\s*:.*)?', title)
        if not match:
            if title.lower().startswith('worldwide caution'):
                continue
            raise AdvisoryValidationError('US title lacks an unambiguous official advisory level.')
        valid_items += 1
        name = match.group(1)
        code = next((c.text for c in item.findall('category') if c.get('domain') == 'Country-Tag'), None)
        try:
            iso3 = resolve_iso3(name, code, allow_regions=True)
        except ValueError:
            if selected is not None:
                raise AdvisoryValidationError('Unmapped US identity prevents reliable subset selection.')
            iso3 = None
        candidates = US_COMPOUND_CANDIDATES.get(name.lower(), [])
        if selected is not None and iso3 not in selected and not selected.intersection(candidates):
            continue
        url = official_url(item.findtext('link'), 'us_state')
        source_key = (item.findtext('guid') or url).strip()
        blocks = paragraphs(item.findtext('description', ''))
        if not source_key or not blocks:
            raise AdvisoryValidationError('US advisory lacks identity or usable body text.')
        regional = name.lower() in {'west bank', 'the west bank', 'gaza', 'saba', 'bonaire'}
        target = {'iso3': iso3, 'scope': 'parts' if regional else 'whole_country', 'region_label': name if regional else None}
        if iso3 is None or candidates:
            target = {'iso3': None, 'scope': 'unresolved', 'region_label': name}
        rows.append({'source': 'us_state', 'source_key': source_key, 'source_url': url,
            'country_name': name, 'fetched_at': fetched_at, 'source_public_updated_at': timestamp(item.findtext('pubDate')),
            'source_updated_at': None, 'source_reviewed_at': None, 'us_level': int(match.group(2)), 'uk_alert_status': None,
            'coverage': [target], 'sections': [{'slug': 'advisory-body', 'title': 'Advisory body', 'paragraphs': blocks}],
            'raw_payload': ET.tostring(item, encoding='utf-8'), 'metadata': {'original_title': title, 'country_tag': code,
                'raw_representation': 'serialized_rss_item', 'covered_iso3_candidates': candidates,
                'mapping_review_required': iso3 is None or bool(candidates), 'original_feed_sha256': hashlib.sha256(body).hexdigest()}})
    if not valid_items:
        raise AdvisoryValidationError('US feed contains no country advisories.')
    return rows


def normalize_bundle(bundle):
    if bundle.get('format') != FORMAT or bundle.get('complete') is not True:
        raise AdvisoryValidationError('Capture is incomplete or has an unknown format.')
    selected = selection(bundle.get('iso3'))
    captures = bundle['captures']
    us = [c for c in captures if c['source'] == 'us_state']
    indices = [c for c in captures if c['source'] == 'uk_index']
    uk = [c for c in captures if c['source'] == 'uk_fcdo']
    if len(us) != 1 or len(indices) != 1 or len(captures) != len(us) + len(indices) + len(uk):
        raise AdvisoryValidationError('Both source captures and the UK index are required.')
    if us[0]['url'] != FEED_URL or indices[0]['url'] != UK_INDEX:
        raise AdvisoryValidationError('Capture endpoint differs from the source contract.')
    targets = uk_targets(json.loads(decode_capture(indices[0])), selected)
    if len({c['url'] for c in uk}) != len(uk) or {c['url'] for c in uk} != set(targets):
        raise AdvisoryValidationError('Captured UK documents do not match the selected index destinations.')
    rows = us_documents(decode_capture(us[0]), timestamp(us[0]['fetched_at']), selected)
    for capture in uk:
        body = decode_capture(capture)
        data = json.loads(body)
        record = normalize_uk(data, allow_unresolved=True)
        if record['source_id'] != targets[capture['url']]['source_key'] or UK_BASE + data['base_path'] != capture['url']:
            raise AdvisoryValidationError('UK document identity differs from its index entry.')
        rows.append({'source': 'uk_fcdo', 'source_key': record['source_id'], 'source_url': official_url(record['source_url'], 'uk_fcdo'),
            'country_name': record['country_name'], 'fetched_at': timestamp(capture['fetched_at']),
            'source_public_updated_at': timestamp(record['source_public_updated_at'], optional=True),
            'source_updated_at': timestamp(record['source_updated_at'], optional=True),
            'source_reviewed_at': timestamp(record['source_reviewed_at'], optional=True),
            'us_level': None, 'uk_alert_status': [w['status'] for w in record['official_warnings']],
            'coverage': coverage(record, record['country_name']), 'sections': record['sections'], 'raw_payload': body,
            'metadata': {'country_name': record['country_name'], 'covered_iso3_candidates': record['covered_iso3'],
                         'mapping_review_required': record['mapping_review_required']}})
    seen = set()
    for row in rows:
        key = (row['source'], row['source_key'])
        if key in seen:
            raise AdvisoryValidationError('Repeated source document identity; review duplicate feed records.')
        seen.add(key)
        row['parser_version'] = PARSER_VERSION
        row['content_sha256'] = hashlib.sha256(row['raw_payload']).hexdigest()
    if not rows:
        raise AdvisoryValidationError('Neither source contains selected destination documents.')
    return rows


def preview(rows, requested=None):
    from collections import defaultdict
    groups = defaultdict(list)
    review = {(r['source'], r['source_key']) for r in rows if any(c['scope'] == 'unresolved' for c in r['coverage'])}
    for row in rows:
        for target in row['coverage']:
            if target['scope'] == 'whole_country':
                groups[(row['source'], target['iso3'])].append(row['source_key'])
    overlaps = []
    for (source, iso3), keys in groups.items():
        if len(keys) > 1:
            overlaps.append({'source': source, 'iso3': iso3, 'source_keys': keys})
            review.update((source, key) for key in keys)
    destinations = set(requested or []) | {c['iso3'] for r in rows for c in r['coverage'] if c['iso3']}
    source_coverage = {}
    for iso3 in sorted(destinations):
        source_coverage[iso3] = {}
        for source in ('us_state', 'uk_fcdo'):
            matching = [r for r in rows if r['source'] == source and any(c['iso3'] == iso3 for c in r['coverage'])]
            pending = any(r['source'] == source and iso3 in r['metadata'].get('covered_iso3_candidates', []) for r in rows)
            source_coverage[iso3][source] = {'status': 'available' if matching else 'review_required' if pending else 'not_in_capture',
                'documents': len(matching), 'scopes': sorted({c['scope'] for r in matching for c in r['coverage'] if c['iso3'] == iso3})}
    return {'parser_version': PARSER_VERSION, 'sources': {s: sum(r['source'] == s for r in rows) for s in ('us_state', 'uk_fcdo')},
            'documents': [{k: v for k, v in row.items() if k != 'raw_payload'} for row in rows],
            'review_required': len(review), 'overlapping_country_documents': overlaps,
            'coverage_by_country': source_coverage, 'public_scores_changed': False}


def capture_bundle(path, iso3=None, *, fetch=None, pause=None):
    """Persist partial capture on failure; ingestion rejects it until complete."""
    import time
    path = Path(path)
    if path.exists():
        raise FileExistsError('Capture output exists.')
    selected = selection(iso3)
    session = None
    if fetch is None:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        session = requests.Session()
        retries = Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504),
                        allowed_methods=('GET',), respect_retry_after_header=False)
        session.mount('https://', HTTPAdapter(max_retries=retries))
        def fetch(url):
            response = session.get(url, timeout=(5, 20), allow_redirects=False)
            if response.status_code != 200:
                raise AdvisoryValidationError('Source request did not return HTTP 200.')
            return response.content
    pause = pause or time.sleep
    bundle = {'format': FORMAT, 'iso3': sorted(selected) if selected else None, 'complete': False, 'captures': []}
    path.parent.mkdir(parents=True, exist_ok=True)
    def save():
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(json.dumps(bundle, indent=2) + '\n')
        temp.replace(path)
    def get(source, url):
        official_url(url, source)
        pause(1)
        body = fetch(url)
        bundle['captures'].append(envelope(source, url, body, datetime.now(timezone.utc).isoformat()))
        save()
        print(f"Captured {len(bundle['captures'])} source responses.", flush=True)
        return body
    with path.open('x') as stream:
        json.dump(bundle, stream, indent=2)
    try:
        index = json.loads(get('uk_index', UK_INDEX))
        targets = uk_targets(index, selected)
        get('us_state', FEED_URL)
        for url in targets:
            get('uk_fcdo', url)
        bundle['complete'] = True
        save()
        return bundle
    finally:
        if session is not None:
            session.close()
