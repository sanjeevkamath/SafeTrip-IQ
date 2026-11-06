"""Security boundaries and before/after verification for the manual refresh workflow."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.configure_refresh_ci import install, scoped_config
from scripts.check_advisory_refresh import check_preflight, check_preview, verify_publication
from safetrip.ingestion.multisource import PARSER_VERSION
from safetrip.scoring.snapshot import calculate, snapshot_hash

RUN = '724cbbdd-bbea-489e-9c3b-e1d44a91e2ee'


def preview(snapshot):
    return {'database_written': False, 'input_snapshot': snapshot, 'input_sha256': snapshot_hash(snapshot),
            'previews': {'exclude': calculate(snapshot)}}


class RefreshTests(unittest.TestCase):
    def config(self, role='writer'):
        roles = {'writer': 'safetrip_writer', 'reader': 'safetrip_reader', 'publisher': 'safetrip_score_publisher'}
        return {'host': 'aws-0.example.pooler.supabase.com', 'port': '5432', 'dbname': 'postgres',
                'user': roles[role] + '.example', 'password': 'synthetic_test_only'}

    def test_admin_wrong_role_host_and_connection_overrides_are_rejected(self):
        self.assertEqual(scoped_config(json.dumps(self.config()), 'writer'), self.config())
        for changes in [{'user': 'postgres.example'}, {'user': 'safetrip_reader.example'},
                        {'host': 'pooler.supabase.com.attacker.example'}, {'port': '6543'},
                        {'options': '-c role=postgres'}, {'sslmode': 'disable'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                scoped_config(json.dumps({**self.config(), **changes}), 'writer')

    def test_credentials_are_not_installed_locally_or_for_mixed_projects(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}), self.assertRaises(ValueError):
            install(['writer'])
        with tempfile.TemporaryDirectory() as directory:
            env = {'GITHUB_ACTIONS': 'true', 'SAFETRIP_WRITER_CONFIG': json.dumps(self.config()),
                   'SAFETRIP_READER_CONFIG': json.dumps({**self.config('reader'), 'user': 'safetrip_reader.other'})}
            with patch('scripts.configure_refresh_ci.ROOT', Path(directory)), patch.dict(os.environ, env), self.assertRaises(ValueError):
                install(['writer', 'reader'])
            self.assertFalse((Path(directory) / '.local').exists())

    def test_runner_files_are_private_refuse_overwrites_and_reject_bad_ca(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {'GITHUB_ACTIONS': 'true', 'SAFETRIP_WRITER_CONFIG': json.dumps(self.config()),
                   'SAFETRIP_DATABASE_CA': 'invalid-pem'}
            with patch('scripts.configure_refresh_ci.ROOT', Path(directory)), patch.dict(os.environ, env):
                with self.assertRaises(Exception):
                    install(['writer'])
                self.assertFalse((Path(directory) / '.local').exists())
                with patch('scripts.configure_refresh_ci.ssl.create_default_context'):
                    install(['writer'])
                    credential = Path(directory) / '.local/supabase/advisory-writer.json'
                    self.assertEqual(credential.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(json.loads(credential.read_text()), self.config())
                    with self.assertRaises(ValueError):
                        install(['writer'])

    def test_missing_sources_keys_or_prior_documents_stop_refresh(self):
        plan = {'format': 'safetrip-hosted-import-plan-v1', 'mode': 'all', 'parser_version': PARSER_VERSION,
                'database_written': False, 'sources': {'us_state': 2, 'uk_fcdo': 3}, 'review_required': 1,
                'database_preflight': {'missing_country_keys': [], 'previous_documents_not_in_capture': []}}
        # An explicitly unresolved compound is retained for review, not guessed into a score.
        self.assertEqual(check_preflight(plan)['review_required_records'], 1)
        for change in [{'sources': {'us_state': 0, 'uk_fcdo': 3}}, {'mode': 'subset'},
                       {'parser_version': 'obsolete'}, {'database_written': True},
                       {'database_preflight': {'missing_country_keys': ['NEW'], 'previous_documents_not_in_capture': []}},
                       {'database_preflight': {'missing_country_keys': [], 'previous_documents_not_in_capture': [{}]}}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                check_preflight({**plan, **change})

    def examples(self):
        countries = [{'iso3': 'CAN', 'name': 'Canada'}, {'iso3': 'PSE', 'name': 'Palestine'}]
        snapshot = {'countries': countries,
                    'published_scores': [{'iso3': 'CAN', 'safe_trip_score': 8.0, 'bert_score': 2, 'clustering_score': 0}],
                    'official_us_advisories': [{'iso3': 'CAN', 'source': 'us_state', 'coverage_scope': 'whole_country', 'us_level': 1},
                                              {'iso3': 'PSE', 'source': 'us_state', 'coverage_scope': 'parts', 'us_level': 4}]}
        before = preview(snapshot)
        after_snapshot = copy.deepcopy(snapshot)
        after_snapshot['published_scores'] = [dict(
            iso3=row['iso3'], safe_trip_score=row['safe_trip_score'],
            bert_score=2 if row['iso3'] == 'CAN' else None, clustering_score=row['clustering_tier'],
            official_us_level=None if row['official_us_level'] is None else str(row['official_us_level']),
            official_us_component=None if row['official_us_component'] is None else str(row['official_us_component']),
            clustering_component=None if row['clustering_component'] is None else str(row['clustering_component']),
            scoring_version='us-official-cluster-v1', score_run_id=RUN, score_published_at='2026-11-05T00:00:00Z'
        ) for row in before['previews']['exclude']['scores']]
        result = {'database_written': True, 'scoring_version': 'us-official-cluster-v1', 'regional_policy': 'exclude',
                  'input_sha256': before['input_sha256'], 'run_id': RUN, 'published_rows': 2}
        return before, preview(after_snapshot), result

    def test_real_formula_verification_handles_nulls_and_text_projection(self):
        before, after, result = self.examples()
        self.assertEqual(check_preview(before)['changed_countries'], 1)
        self.assertEqual(verify_publication(before, after, result)['verified_rows'], 2)

    def test_tampered_preview_or_conflicting_whole_country_levels_stop_publication(self):
        before, _, _ = self.examples()
        tampered = copy.deepcopy(before)
        tampered['previews']['exclude']['scores'][0]['safe_trip_score'] = 1
        with self.assertRaises(ValueError):
            check_preview(tampered)
        conflict = copy.deepcopy(before['input_snapshot'])
        conflict['official_us_advisories'].append({'iso3': 'CAN', 'source': 'us_state', 'coverage_scope': 'whole_country', 'us_level': 4})
        with self.assertRaises(ValueError):
            check_preview(preview(conflict))

    def test_changed_model_input_run_missing_row_or_score_fails_readback(self):
        before, after, result = self.examples()
        for field, value in [('bert_score', 3), ('clustering_score', 2), ('score_run_id', 'other'),
                             ('safe_trip_score', 1), ('official_us_component', '7.5'),
                             ('official_us_component', 'NaN')]:
            damaged = copy.deepcopy(after['input_snapshot'])
            damaged['published_scores'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_publication(before, preview(damaged), result)
        damaged = copy.deepcopy(after['input_snapshot'])
        damaged['published_scores'].pop()
        with self.assertRaises(ValueError):
            verify_publication(before, preview(damaged), result)


if __name__ == '__main__':
    unittest.main()
