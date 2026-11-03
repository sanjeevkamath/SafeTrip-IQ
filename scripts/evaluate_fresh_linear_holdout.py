"""Evaluate the validation-selected linear baseline once on the fresh feed."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from scripts.evaluate_bert_validation import metrics

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / '.local/research/bert/dataset-v3c')
    parser.add_argument('--investigation', type=Path, default=ROOT / '.local/research/bert/investigation-v3c')
    parser.add_argument('--holdout', type=Path, default=ROOT / '.local/research/bert/fresh-holdout-v3')
    args = parser.parse_args()
    output = args.investigation / 'linear-fresh-evaluation.json'
    if output.exists():
        raise FileExistsError('Fresh evaluation already exists; retain its original result.')
    validation_path = args.investigation / 'linear-validation.json'
    validation = json.loads(validation_path.read_text())
    dataset_manifest = args.dataset / 'manifest.json'
    manifest = json.loads(dataset_manifest.read_text())
    holdout_manifest = args.holdout / 'manifest.json'
    fresh = json.loads(holdout_manifest.read_text())
    if not (digest(dataset_manifest) == validation['dataset_manifest_sha256'] == fresh['historical_manifest_sha256']):
        raise ValueError('Training, validation, and holdout filtering must share one dataset.')
    train_path = args.dataset / 'train.jsonl'
    source = args.holdout / 'holdout.jsonl'
    if digest(train_path) != manifest['artifacts']['train.jsonl'] or digest(source) != fresh['holdout_sha256']:
        raise ValueError('Input changed since preparation.')
    selected = max(validation['experiments'], key=lambda row: row['metrics']['macro_f1'])['C']
    if selected != validation['selected_C']:
        raise ValueError('Stored selection disagrees with validation results.')
    choice = {'C': selected, 'criterion': 'highest validation macro-F1',
              'holdout_used_for_selection': False, 'validation_sha256': digest(validation_path),
              'dataset_manifest_sha256': digest(dataset_manifest)}
    lock = args.investigation / 'linear-selection-lock.json'
    if lock.exists():
        if json.loads(lock.read_text()) != choice:
            raise ValueError('Selection was already locked differently.')
    else:
        with lock.open('x') as stream:
            json.dump(choice, stream, indent=2)
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from threadpoolctl import threadpool_limits
    train = [json.loads(line) for line in train_path.read_text().splitlines()]
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    started = time.monotonic()
    with threadpool_limits(limits=2):
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=20000)
        matrix = vectorizer.fit_transform([r['text'] for r in train])
        classifier = LogisticRegression(C=selected, class_weight='balanced', max_iter=2000, random_state=42)
        classifier.fit(matrix, [r['label'] for r in train])
        predictions = [int(v) for v in classifier.predict(vectorizer.transform([r['text'] for r in rows]))]
    report = {'experiment': 'linear', 'selection': choice, 'split': 'fresh_official_feed_filtered',
              'holdout_manifest_sha256': digest(holdout_manifest), 'rows': len(rows),
              'seconds_including_fit': round(time.monotonic() - started, 3),
              'metrics': metrics([r['label'] for r in rows], predictions),
              'predictions': [{'text_sha256': r['text_sha256'], 'group_id': r['group_id'],
                               'label': r['label'], 'prediction': prediction}
                              for r, prediction in zip(rows, predictions)],
              'limitations': fresh['limitations']}
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report['metrics'], indent=2))


if __name__ == '__main__':
    main()
