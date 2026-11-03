import unittest
from scripts.check_publish_ci import verified_run

SHA = 'a' * 40
REPO = 'sanjeevkamath/SafeTrip-IQ'


class PublishingGateTests(unittest.TestCase):
    def run_record(self, **changes):
        return dict({'id': 123, 'head_sha': SHA, 'head_branch': 'main',
                     'head_repository': {'full_name': REPO}, 'event': 'push',
                     'status': 'completed', 'conclusion': 'success'}, **changes)

    def test_exact_main_commit_with_successful_ci(self):
        self.assertEqual(verified_run({'workflow_runs': [self.run_record()]}, SHA, REPO), 123)

    def test_failed_pending_old_fork_and_pr_runs_cannot_authorize_publishing(self):
        for changes in [{'conclusion': 'failure'}, {'status': 'in_progress'}, {'head_sha': 'b'*40},
                        {'head_branch': 'other'}, {'event': 'pull_request'},
                        {'head_repository': {'full_name': 'fork/SafeTrip-IQ'}}, {'head_repository': None}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                verified_run({'workflow_runs': [self.run_record(**changes)]}, SHA, REPO)

    def test_earlier_success_does_not_override_latest_failure_or_pending_run(self):
        for changes in [{'conclusion': 'failure'}, {'status': 'in_progress', 'conclusion': None}]:
            latest = self.run_record(**changes)
            latest['id'] = 124
            with self.assertRaises(ValueError):
                verified_run({'workflow_runs': [self.run_record(), latest]}, SHA, REPO)

    def test_no_ci_or_invalid_sha_fails_closed(self):
        for sha in [SHA, 'main', 'a'*39]:
            with self.assertRaises(ValueError): verified_run({'workflow_runs': []}, sha, REPO)


if __name__ == '__main__': unittest.main()
