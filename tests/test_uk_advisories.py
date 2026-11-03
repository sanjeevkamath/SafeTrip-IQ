import unittest
from safetrip.ingestion.uk_advisories import destination, normalize_uk, paragraphs


class UKAdvisoryTests(unittest.TestCase):
    def document(self, alerts):
        return {'document_type':'travel_advice','content_id':'test','base_path':'/foreign-travel-advice/india',
                'details':{'country':{'name':'India','slug':'india'},'alert_status':alerts,
                'parts':[{'slug':'safety-and-security','title':'Safety and security',
                          'body':'<h2>Crime</h2><p>Armed <strong>robbery</strong> occurs.</p>'},
                         {'slug':'entry-requirements','title':'Entry','body':'<p>Visa required.</p>'}]}}

    def test_region_flags_are_not_whole_country_levels(self):
        doc=normalize_uk(self.document(['avoid_all_travel_to_parts','avoid_all_but_essential_travel_to_parts']))
        self.assertEqual(doc['iso3'],'IND')
        self.assertTrue(all(w['scope']=='parts' for w in doc['official_warnings']))
        self.assertNotIn('official_level',doc)
        self.assertEqual(len(doc['sections']),1)

    def test_unknown_or_missing_alerts_fail(self):
        for alerts in [None,['new_unknown_status']]:
            with self.assertRaises(ValueError):normalize_uk(self.document(alerts))
        self.assertEqual(normalize_uk(self.document([]))['official_warnings'],[])

    def test_combined_territory_is_not_assigned_one_country(self):
        result=destination({'name':'St Martin and St Barthélemy','slug':'st-martin-and-st-barthelemy'})
        self.assertIsNone(result['iso3'])
        self.assertEqual(result['covered_iso3'],['MAF','BLM'])
        self.assertTrue(result['mapping_review_required'])

    def test_html_boundaries_entities_and_hidden_content(self):
        result=paragraphs('<h2>Crime</h2><p>Robbery &amp; theft.</p><script>Danger</script><p>Use caution.</p>')
        self.assertEqual(result,[{'heading':'Crime','text':'Robbery & theft.'},{'heading':'Crime','text':'Use caution.'}])


if __name__=='__main__':unittest.main()
