import json
import unittest
from safetrip.ingestion.uk_advisories import paragraphs
from safetrip.ingestion.uk_warning_areas import warning_areas,checked_references


def payload(body, flags=None):
    return json.dumps({'details':{'alert_status':flags if flags is not None else ['avoid_all_travel_to_parts'],
        'parts':[{'slug':'warnings-and-insurance','body':body}]}}).encode()


class UKWarningAreaTests(unittest.TestCase):
    def test_exact_limits_exceptions_lists_and_parent_warning_are_preserved(self):
        body='''<p>Insurance introduction.</p><h2>Areas where FCDO advises against travel</h2>
        <h3>Eastern border</h3><p>FCDO advises against all travel within 5km, except the official crossing:</p>
        <ul><li>Road A</li><li>Road B</li></ul><p>The exception applies only during daylight.</p>
        <h2>Before you travel</h2><p>General travel guidance.</p>'''
        blocks,refs=warning_areas(payload(body))
        self.assertEqual(blocks,paragraphs(body))
        text=[blocks[r['paragraph_index']]['text'] for r in refs]
        self.assertEqual(text,['FCDO advises against all travel within 5km, except the official crossing:',
                               'Road A','Road B','The exception applies only during daylight.'])
        self.assertTrue(all(r['warning_heading']=='Areas where FCDO advises against travel' for r in refs))

    def test_sibling_area_headings_exclude_unrelated_risk_sections(self):
        body='''<h2>Areas where FCDO advises against travel</h2><h2>Southern border</h2>
        <p>FCDO also advises against all but essential travel to the border districts:</p>
        <ul><li>District One</li><li>District Two, except its city centre</li></ul>
        <h2>Flooding</h2><p>Flooding occurs in Capital City.</p>
        <h2>Other border</h2><p>This border is closed.</p>'''
        blocks,refs=warning_areas(payload(body))
        self.assertEqual(len(refs),3)
        self.assertNotIn('Flooding occurs in Capital City.',[blocks[r['paragraph_index']]['text'] for r in refs])

    def test_general_historical_and_negated_text_does_not_open_a_warning_block(self):
        for text in ['FCDO no longer advises against all travel to this area.',
                     'FCDO previously advised against all travel to this area.',
                     'Read FCDO safety guidance before travelling.']:
            with self.subTest(text=text):
                self.assertEqual(warning_areas(payload('<h2>Border information</h2><p>'+text+'</p>'))[1],[])

    def test_no_regional_flags_and_unstructured_text_use_no_inferred_area(self):
        body='<h2>Areas where FCDO advises against travel</h2><p>Border warning.</p>'
        self.assertEqual(warning_areas(payload(body,[])),([],[]))
        self.assertEqual(warning_areas(payload('<p>Risks exist near the border.</p>'))[1],[])

    def test_references_cannot_attach_to_changed_or_missing_stored_paragraphs(self):
        raw=payload('<h2>Areas where FCDO advises against travel</h2><p>Within 5km, except the main crossing.</p>')
        blocks,refs=warning_areas(raw)
        expected={i:p for i,p in enumerate(blocks)}
        self.assertEqual(checked_references(raw,expected),refs)
        for stored in [{},{0:{'heading':'Different','text':'Changed text'}}]:
            with self.assertRaises(ValueError):checked_references(raw,stored)
