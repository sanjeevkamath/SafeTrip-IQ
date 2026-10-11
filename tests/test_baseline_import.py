import copy
import tempfile
from pathlib import Path
import unittest

from safetrip.persistence.baseline import TABLES, load_baseline, validate_tables


class BaselineImportTests(unittest.TestCase):
    def example(self):
        tables = {table:[] for table in TABLES}
        tables.update(countries=[{'iso3':'AAA','name':'Example'},{'iso3':'BBB','name':'Missing'}],
                      bert_scores=[{'iso3':'AAA','bert_score':0}],
                      clustering=[{'iso3':'AAA','clustering_score':0}],
                      scores=[{'iso3':'AAA','bert_score':0,'clustering_score':0,'safe_trip_score':10}])
        return tables

    def test_mapping_and_missingness_validated(self):
        report = validate_tables(self.example(), {'AAA':1})
        self.assertEqual(report['coverage'], dict(both=1, bert_only=0, clustering_only=0, neither=1))

    def test_corruption_and_unresolved_references_rejected(self):
        for change in ('tier','score','orphan','duplicate'):
            tables = copy.deepcopy(self.example())
            if change == 'tier': tables['clustering'][0]['clustering_score'] = 1
            if change == 'score': tables['scores'][0]['safe_trip_score'] = 0
            if change == 'orphan': tables['culture'] = [{'iso3':'ZZZ'}]
            if change == 'duplicate': tables['countries'].append(tables['countries'][0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_tables(tables, {'AAA':1})

    def test_unreviewed_manifest_rejected_before_data_is_read(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'reviewed legacy release'):
                load_baseline(directory, 'unused.csv')
