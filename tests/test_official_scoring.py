import unittest
from safetrip.scoring.official import component_score,select_us_level,preview_scores
from safetrip.scoring.legacy import legacy_safety_score


def document(level=2,scope='whole_country',iso3='CAN'):
    return {'iso3':iso3,'source':'us_state','us_level':level,'coverage_scope':scope,
            'version_id':'version','region_label':None if scope=='whole_country' else 'Border'}


class OfficialScoringTests(unittest.TestCase):
    def test_replacement_preserves_legacy_conversions_with_correct_level_offset(self):
        for level in [1,2,3,4]:
            for tier in [None,0,1,2,3,4]:
                with self.subTest(level=level,tier=tier):
                    self.assertEqual(component_score(level,tier)['safe_trip_score'],legacy_safety_score(level-1,tier))
        self.assertEqual(component_score(2,2)['safe_trip_score'],6.75)

    def test_missing_components_do_not_become_zero_and_level4_remains_explicit(self):
        self.assertEqual(component_score(None,2)['safe_trip_score'],6)
        self.assertEqual(component_score(4,None)['safe_trip_score'],2.5)
        self.assertIsNone(component_score(None,None)['safe_trip_score'])
        self.assertTrue(component_score(4,0)['severe_official_warning'])
        self.assertEqual(component_score(None,None)['coverage'],'neither')

    def test_invalid_values_are_not_coerced_or_clipped(self):
        for value in [0,5,True,1.0,'1']:
            with self.assertRaises(ValueError):component_score(value,0)
        for value in [-1,5,True,1.0,'1']:
            with self.assertRaises(ValueError):component_score(1,value)

    def test_duplicate_agreement_conflict_and_regional_policies_are_explicit(self):
        self.assertEqual(select_us_level([document(2),document(2)],'exclude'),(2,'matching_whole_country_advisories'))
        self.assertEqual(select_us_level([document(1),document(4)],'exclude'),(None,'conflicting_whole_country_advisories'))
        regional=[document(3,'parts'),document(4,'parts')]
        self.assertEqual(select_us_level(regional,'exclude'),(None,'regional_only_excluded'))
        self.assertEqual(select_us_level(regional,'highest'),(4,'highest_regional_level'))
        self.assertEqual(select_us_level([document(2),*regional],'highest'),(2,'whole_country'))

    def test_old_bert_prediction_cannot_change_the_new_score(self):
        countries=[{'iso3':'CAN','name':'Canada'},{'iso3':'USA','name':'United States'}]
        old={'CAN':{'safe_trip_score':10,'bert_score':0,'clustering_score':2}}
        a=preview_scores(countries,old,[document(2)],'exclude')
        old['CAN']['bert_score']=3
        b=preview_scores(countries,old,[document(2)],'exclude')
        self.assertEqual(a['scores'][0]['safe_trip_score'],b['scores'][0]['safe_trip_score'])
        self.assertEqual(a['scores'][0]['safe_trip_score'],6.75)
        self.assertEqual(a['changed_countries'],1)
        self.assertIsNone(a['scores'][1]['safe_trip_score'])
        self.assertFalse(a['database_written'])
