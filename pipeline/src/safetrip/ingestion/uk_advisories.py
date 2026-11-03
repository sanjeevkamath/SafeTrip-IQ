"""Read-only normalization of FCDO Content API documents; no score or persistence."""
from html.parser import HTMLParser
import re

from .countries import resolve_iso3

RISK_PARTS = {'warnings-and-insurance', 'safety-and-security', 'regional-risks', 'health'}
KNOWN_ALERTS = {
    'avoid_all_travel_to_whole_country': ('all_travel', 'whole_country'),
    'avoid_all_but_essential_travel_to_whole_country': ('essential_only', 'whole_country'),
    'avoid_all_travel_to_parts': ('all_travel', 'parts'),
    'avoid_all_but_essential_travel_to_parts': ('essential_only', 'parts'),
}
UK_ALIASES = {'usa': 'USA', 'palestine': 'PSE', 'cape verde': 'CPV',
              'st kitts and nevis': 'KNA', 'st lucia': 'LCA', 'st maarten': 'SXM',
              'st pierre & miquelon': 'SPM', 'st vincent and the grenadines': 'VCT',
              'pitcairn island': 'PCN', 'falkland islands': 'FLK',
              'bonaire/st eustatius/saba': 'BES',
              'st helena, ascension and tristan da cunha': 'SHN'}
MULTI_DESTINATIONS = {'st-martin-and-st-barthelemy': ['MAF', 'BLM'],
                      'cook-islands-tokelau-and-niue': ['COK', 'TKL', 'NIU'],
                      'antarctica-british-antarctic-territory': ['ATA']}


class ParagraphParser(HTMLParser):
    """Retain paragraph boundaries and headings; remove script/style text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.buffer, self.hidden = [], [], 0
        self.heading = None
        self.in_heading = False

    def flush(self):
        text = re.sub(r'\s+', ' ', ''.join(self.buffer)).strip()
        if text:
            if self.in_heading:
                self.heading = text
            else:
                self.blocks.append({'heading': self.heading, 'text': text})
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script','style'}: self.hidden += 1
        if self.hidden: return
        if tag in {'p','li','h1','h2','h3','h4','blockquote','br'}:
            self.flush()
        if tag in {'h1','h2','h3','h4'}: self.in_heading = True

    def handle_endtag(self, tag):
        if tag in {'script','style'}:
            self.hidden = max(0,self.hidden-1)
            return
        if self.hidden: return
        if tag in {'p','li','h1','h2','h3','h4','blockquote'}:
            self.flush()
        if tag in {'h1','h2','h3','h4'}: self.in_heading = False

    def handle_data(self, data):
        if not self.hidden: self.buffer.append(data)


def paragraphs(body):
    parser = ParagraphParser()
    parser.feed(body)
    parser.flush()
    return parser.blocks


def destination(country):
    slug, name = country['slug'], country['name']
    if slug in MULTI_DESTINATIONS:
        return {'iso3': None, 'covered_iso3': MULTI_DESTINATIONS[slug], 'mapping_review_required': True}
    iso3 = UK_ALIASES.get(name.lower()) or resolve_iso3(name, None, allow_regions=True)
    return {'iso3': iso3, 'covered_iso3': [iso3], 'mapping_review_required': False}


def normalize_uk(data):
    if data.get('document_type') != 'travel_advice' or data.get('withdrawn'):
        raise ValueError('Expected active travel-advice document.')
    details = data['details']
    identity = destination(details['country'])
    alerts = details.get('alert_status')
    if not isinstance(alerts,list) or any(a not in KNOWN_ALERTS for a in alerts):
        raise ValueError('Unknown or missing UK warning status; review before use.')
    sections = []
    for part in details['parts']:
        if part['slug'] in RISK_PARTS:
            sections.append({'slug':part['slug'], 'title':part['title'].strip(),
                             'paragraphs':paragraphs(part['body'])})
    if not sections or not any(s['paragraphs'] for s in sections):
        raise ValueError('No risk text found.')
    base = data['base_path']
    if not base.startswith('/foreign-travel-advice/'): raise ValueError('Unexpected canonical path.')
    return {'source':'uk_fcdo', 'source_id':data['content_id'], 'country_name':details['country']['name'],
            **identity, 'source_url':'https://www.gov.uk'+base,
            'source_public_updated_at':data.get('public_updated_at'),
            'source_updated_at':details.get('updated_at'), 'source_reviewed_at':details.get('reviewed_at'),
            'official_warnings':[{'status':a,'restriction':KNOWN_ALERTS[a][0],'scope':KNOWN_ALERTS[a][1]} for a in alerts],
            'sections':sections}
