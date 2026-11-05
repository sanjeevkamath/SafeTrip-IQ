"""Conservative references to official warning blocks, not inferred geography."""
import json
import re
from .uk_advisories import ParagraphParser

EXTRACTOR_VERSION = 'uk-warning-areas-v1'
SECTION = 'warnings-and-insurance'
REGIONAL_FLAGS = {'avoid_all_travel_to_parts', 'avoid_all_but_essential_travel_to_parts'}


class WarningParser(ParagraphParser):
    def __init__(self):
        super().__init__()
        self.level = 0
        self.warning = None
        self.warning_level = None
        self.references = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if not self.hidden and tag in {'h1','h2','h3','h4'}:
            self.level = int(tag[1])

    def flush(self):
        has_text = bool(''.join(self.buffer).strip())
        is_heading = self.in_heading
        previous = len(self.blocks)
        super().flush()
        if is_heading and has_text:
            if self.warning_level is not None and self.level <= self.warning_level:
                self.warning = self.warning_level = None
            # Only explicit FCDO warning headings open a block. General risk,
            # closed-border and historical headings do not become restrictions.
            if re.search(r'\bFCDO\b.*\badvises against\b.*\btravel\b', self.heading, re.I):
                self.warning, self.warning_level = self.heading, self.level
        else:
            if (not self.warning and len(self.blocks)>previous and self.heading
                and re.search(r'\bFCDO\s+(?:also\s+)?advises against\s+(?:all travel|all but essential travel)\b',
                              self.blocks[previous]['text'],re.I)):
                # Some pages use sibling h2 area headings after the warning
                # banner. Require an explicit present-tense restriction here.
                self.warning, self.warning_level = self.heading, self.level
            for index in range(previous,len(self.blocks)):
                if self.warning:
                    self.references.append({'section_slug':SECTION,'paragraph_index':index,
                                            'warning_heading':self.warning})


def warning_areas(raw_payload):
    data = json.loads(raw_payload)
    if not REGIONAL_FLAGS.intersection(data['details'].get('alert_status') or []):
        return [], []
    part = next((p for p in data['details']['parts'] if p['slug'] == SECTION), None)
    if part is None:
        return [], []
    parser = WarningParser()
    parser.feed(part['body'])
    parser.flush()
    return parser.blocks, parser.references


def checked_references(raw_payload, stored_paragraphs):
    """Refuse to attach references if parsing differs from the stored version."""
    blocks, references = warning_areas(raw_payload)
    for ref in references:
        index = ref['paragraph_index']
        if stored_paragraphs.get(index) != blocks[index]:
            raise ValueError('Warning extraction differs from stored paragraph provenance.')
    return references
