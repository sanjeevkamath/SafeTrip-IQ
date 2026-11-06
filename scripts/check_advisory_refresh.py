"""Fail closed on incomplete imports and verify committed official-score outputs."""
import argparse
import json
import math
import os
from pathlib import Path
import uuid


def check_preflight(plan):
    from safetrip.ingestion.multisource import PARSER_VERSION
    if (plan.get('format') != 'safetrip-hosted-import-plan-v1' or plan.get('mode') != 'all'
            or plan.get('parser_version') != PARSER_VERSION or plan.get('database_written') is not False):
        raise ValueError('Expected a full, current-parser preflight')
    sources = plan.get('sources', {})
    if not all(type(sources.get(s)) is int and sources[s] > 0 for s in ['us_state', 'uk_fcdo']):
        raise ValueError('Both sources must contain documents')
    catalogue = plan.get('database_preflight', {})
    if catalogue.get('missing_country_keys') != [] or catalogue.get('previous_documents_not_in_capture') != []:
        raise ValueError('Missing country keys or previously stored source documents require review')
    return {'source_documents': sources, 'unresolved_records': plan['review_required']}


def check_preview(report):
    from safetrip.scoring.snapshot import calculate, snapshot_hash
    if report.get('database_written') is not False or set(report.get('previews', {})) != {'exclude'}:
        raise ValueError('Expected a read-only regional-exclusion preview')
    snapshot = report['input_snapshot']
    if report['input_sha256'] != snapshot_hash(snapshot):
        raise ValueError('Preview input checksum differs')
    expected = calculate(snapshot)
    if expected != report['previews']['exclude'] or expected['review_required'] or not expected['scores']:
        raise ValueError('Scoring conflict or invalid preview requires review')
    return {'coverage': expected['coverage'], 'changed_countries': expected['changed_countries'],
            'input_sha256': report['input_sha256'], 'regional_policy': 'exclude'}


def verify_publication(before, after, result):
    check_preview(before)
    check_preview(after)
    run = str(uuid.UUID(result['run_id']))
    if (result.get('database_written') is not True or result.get('scoring_version') != 'us-official-cluster-v1'
            or result.get('regional_policy') != 'exclude' or result.get('input_sha256') != before['input_sha256']):
        raise ValueError('Publication does not match the reviewed snapshot')
    old = {r['iso3'].strip(): r for r in before['input_snapshot']['published_scores']}
    new = {r['iso3'].strip(): r for r in after['input_snapshot']['published_scores']}
    expected = {r['iso3']: r for r in before['previews']['exclude']['scores']}
    if set(new) != set(expected) or result['published_rows'] != len(new):
        raise ValueError('Published country coverage differs')
    for iso, row in new.items():
        if (row['scoring_version'] != result['scoring_version'] or str(row['score_run_id']) != run
                or not row['score_published_at']):
            raise ValueError('Published formula/run provenance differs')
        for field in ['bert_score', 'clustering_score']:
            if row[field] != old.get(iso, {}).get(field):
                raise ValueError('Historical model inputs changed')
        for field in ['safe_trip_score', 'official_us_component', 'clustering_component', 'official_us_level']:
            actual, wanted = row[field], expected[iso][field]
            # Optional metadata is read through to_jsonb ->>, so it arrives as text.
            actual = None if actual is None else float(actual)
            if ((actual is None) != (wanted is None)
                    or (actual is not None and (not math.isfinite(actual) or abs(actual - wanted) > 0.00001))):
                raise ValueError('Published score differs from the reviewed result')
    if after['previews']['exclude']['changed_countries'] != 0:
        raise ValueError('Current source inputs have changed since publication; review before retrying')
    return {'verified_rows': len(new), 'run_id': run, 'historical_inputs_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['preflight', 'preview', 'verify'])
    parser.add_argument('--input', required=True)
    parser.add_argument('--after')
    parser.add_argument('--publication')
    args = parser.parse_args()
    try:
        report = json.loads(Path(args.input).read_text())
        if args.stage == 'preflight':
            summary = check_preflight(report)
        elif args.stage == 'preview':
            summary = check_preview(report)
        else:
            summary = verify_publication(report, json.loads(Path(args.after).read_text()),
                                         json.loads(Path(args.publication).read_text()))
        print(json.dumps(summary, sort_keys=True))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
                stream.write(f'### Advisory refresh: {args.stage}\n\n```json\n{json.dumps(summary, indent=2)}\n```\n\n')
    except Exception:
        parser.exit(1, 'Refresh validation stopped. Review the saved artifacts and run ledger; details suppressed.\n')


if __name__ == '__main__':
    main()
