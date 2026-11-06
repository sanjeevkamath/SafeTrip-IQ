"""Require a recorded, successful manual import + publication + read-back run."""
import argparse
import json
import re
import subprocess


def verify_run(run, jobs, repository):
    if (run.get('event') != 'workflow_dispatch' or run.get('head_branch') != 'main'
            or run.get('path') != '.github/workflows/refresh-advisories.yml'
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or (run.get('repository') or {}).get('full_name') != repository):
        raise ValueError('Expected a successful manual production refresh')
    current = {job['name']: job for job in jobs['jobs']}
    if any(current.get(name, {}).get('conclusion') != 'success' for name in ['refresh', 'publish']):
        raise ValueError('Both import and publication must succeed; a skipped publisher is insufficient')
    steps = current['publish'].get('steps', [])
    if not any(s.get('name') == 'Independently read back outputs and verify preserved model inputs'
               and s.get('conclusion') == 'success' for s in steps):
        raise ValueError('Successful independent read-back verification is required')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True)
    p.add_argument('--repository', required=True)
    args = p.parse_args()
    try:
        if not re.fullmatch(r'[0-9]+', args.run) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
            raise ValueError('Invalid run or repository')
        def api(path):
            return json.loads(subprocess.run(['gh', 'api', path], check=True, capture_output=True, text=True).stdout)
        base = f'repos/{args.repository}/actions/runs/{args.run}'
        verify_run(api(base), api(base + '/jobs?filter=latest&per_page=100'), args.repository)
        print('Verified manual end-to-end refresh run:', args.run)
    except Exception:
        p.exit(1, 'Scheduled refresh blocked: configure a successful manual import/publication/read-back run first.\n')


if __name__ == '__main__':
    main()
