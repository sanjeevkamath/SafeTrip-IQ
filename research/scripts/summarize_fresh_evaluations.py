"""Summarize existing fresh reports with paired group-bootstrap uncertainty."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random

from research.scripts.evaluate_bert_validation import metrics

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--investigation', type=Path, default=ROOT / '.local/research/bert/investigation-v3c')
    args = parser.parse_args()
    reports = [json.loads(path.read_text()) for path in sorted(args.investigation.glob('*-fresh-evaluation.json'))]
    if len(reports) < 2:
        raise ValueError('Need at least two locked model evaluation reports.')
    first = reports[0]
    keys = [(r['text_sha256'], r['group_id'], r['label']) for r in first['predictions']]
    for report in reports:
        if report['holdout_manifest_sha256'] != first['holdout_manifest_sha256'] or keys != [
                (r['text_sha256'], r['group_id'], r['label']) for r in report['predictions']]:
            raise ValueError('Reports must evaluate identical documents in identical order.')
    groups = defaultdict(list)
    for index, (_, group, _) in enumerate(keys):
        groups[group].append(index)
    group_ids = sorted(groups)
    labels = [r['label'] for r in first['predictions']]
    statistics = ('accuracy', 'macro_f1', 'high_risk_underestimation_rate')
    samples = {r['experiment']: {key: [] for key in statistics} for r in reports}
    generator = random.Random(42)
    for _ in range(2000):
        indices = [i for group in generator.choices(group_ids, k=len(group_ids)) for i in groups[group]]
        actual = [labels[i] for i in indices]
        for report in reports:
            result = metrics(actual, [report['predictions'][i]['prediction'] for i in indices])
            for key in statistics:
                samples[report['experiment']][key].append(result[key])
    def interval(values):
        ordered = sorted(v for v in values if v is not None)
        return [ordered[int(.025 * (len(ordered) - 1))], ordered[int(.975 * (len(ordered) - 1))]]
    result = {'rows': len(labels), 'groups': len(groups), 'bootstrap_draws': 2000, 'seed': 42,
              'holdout_manifest_sha256': first['holdout_manifest_sha256'],
              'limitation': 'Percentile group bootstrap reflects this feed sample, not unknown provenance, label noise, or future temporal shifts.',
              'models': {r['experiment']: {'metrics': r['metrics'], 'approximate_95_percent_intervals': {
                  key: interval(values) for key, values in samples[r['experiment']].items()}} for r in reports},
              'paired_macro_f1_differences': {}}
    for index, a in enumerate(reports):
        for b in reports[index + 1:]:
            name_a, name_b = a['experiment'], b['experiment']
            differences = [x-y for x,y in zip(samples[name_a]['macro_f1'], samples[name_b]['macro_f1'])]
            result['paired_macro_f1_differences'][name_a + ' minus ' + name_b] = interval(differences)
    target = args.investigation / 'fresh-summary.json'
    with target.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
