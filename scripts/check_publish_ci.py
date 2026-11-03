"""Require successful main-branch CI for the exact commit before AWS authentication."""
import argparse
import json
import re
import sys


def verified_run(payload, sha, repository):
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Expected a full commit SHA.')
    candidates = [run for run in payload.get('workflow_runs', [])
                  if run.get('head_sha') == sha and run.get('head_branch') == 'main'
                  and (run.get('head_repository') or {}).get('full_name') == repository
                  and run.get('event') in {'push', 'workflow_dispatch'}]
    if candidates:
        latest = max(candidates, key=lambda run: (int(run['id']), int(run.get('run_attempt', 1))))
        if latest.get('status') == 'completed' and latest.get('conclusion') == 'success':
            return latest['id']
    raise ValueError('Latest main-branch CI for this repository and commit must have succeeded.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--repository', required=True)
    args = parser.parse_args()
    try:
        run_id = verified_run(json.load(sys.stdin), args.sha, args.repository)
    except (ValueError, KeyError, TypeError):
        parser.exit(1, 'Publishing stopped: successful main-branch CI for this commit is required.\n')
    print(f'Verified CI run: {run_id}')


if __name__ == '__main__':
    main()
