"""Audit source labels and frozen predictions; run validation-only linear ablations."""
import csv
import hashlib
import json
from pathlib import Path
import re
from collections import Counter, defaultdict

from research.scripts.evaluate_bert_validation import metrics
from safetrip.ingestion.advisories import clean_html_to_text, LEVEL_PATTERN, RECOMMENDATION_PATTERN

ROOT = Path(__file__).resolve().parents[2]
COVID = re.compile(r'covid|coronavirus', re.I)
# First standard recommendation is a consistency screen, not verified source metadata.
CUES = re.compile(r'\b(exercise normal precautions?|exercise increased caution|reconsider travel|do not travel)\b', re.I)
CUE_LABELS = {'exercise normal precaution': 0, 'exercise normal precautions': 0,
              'exercise increased caution': 1, 'reconsider travel': 2, 'do not travel': 3}
# Sentence-level research interventions; not proposed production cleaners.
HEALTH_SENTENCE = re.compile(r'[^.!?]*(?:covid[^.!?]*|coronavirus[^.!?]*|centers for disease control[^.!?]*|\bcdc\b[^.!?]*)[.!?]?', re.I)
SEVERITY = re.compile(r'\b(?:very high|moderate|high|unknown)\s+(?:level|levels)\b', re.I)
GENERIC_SENTENCE = re.compile(r'[^.!?]*(?:read the country information|if you decide to travel|follow the department of state|traveler.?s checklist|enroll in[^.!?]*step)[^.!?]*[.!?]?', re.I)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subgroup(rows, predictions):
    result = {}
    for name, flag in [('covid_mention', True), ('no_covid_mention', False)]:
        indices = [i for i, row in enumerate(rows) if bool(COVID.search(row['text'])) == flag]
        actual = [rows[i]['label'] for i in indices]
        result[name] = {'rows': len(indices), 'class_counts': dict(sorted(Counter(a+1 for a in actual).items())),
                        'metrics': metrics(actual, [predictions[i] for i in indices]) if indices else None}
    return result


def main():
    dataset = ROOT / '.local/research/bert/dataset-v3c'
    investigation = ROOT / '.local/research/bert/investigation-v3c'
    target = investigation / 'label-transfer-audit.json'
    if target.exists():
        raise FileExistsError('Audit already exists; preserve it.')
    manifest = json.loads((dataset/'manifest.json').read_text())
    splits = {}
    for split in ['train', 'validation']:
        path = dataset/(split+'.jsonl')
        if digest(path) != manifest['artifacts'][path.name]:
            raise ValueError('Dataset changed.')
        splits[split] = [json.loads(line) for line in path.read_text().splitlines()]
    raw = {}
    for split in ['train','test']:
        path = ROOT/f'data/baseline/bert/{split}.csv'
        if digest(path) != manifest['source_hashes'][split]:
            raise ValueError('Source changed.')
        raw[split] = list(csv.DictReader(path.open()))
    audit = {}
    for split, rows in splits.items():
        findings = defaultdict(list)
        for row in rows:
            if LEVEL_PATTERN.search(row['text']): findings['retained_numeric_level'].append(row['text_sha256'])
            if RECOMMENDATION_PATTERN.search(row['text']): findings['retained_recommendation'].append(row['text_sha256'])
            for ref in row['source_rows']:
                original = raw[ref['source_split']][ref['source_row']-2]
                if int(original['label'])-1 != row['label']:
                    raise ValueError('Label transformation disagrees with source.')
                matches = list(CUES.finditer(original['text'][:800]))
                key = 'leading_cue_unresolved'
                if matches:
                    inferred = CUE_LABELS[matches[0].group().lower()]
                    key = 'leading_cue_agrees' if inferred == row['label'] else 'leading_cue_disagrees'
                findings[key].append({'source': ref, 'stored_level': row['label']+1,
                    'first_cue': matches[0].group() if matches else None,
                    'raw_excerpt': original['text'][:450]} if key != 'leading_cue_agrees' else ref)
        audit[split] = {'rows':len(rows), 'checked_source_references':sum(len(r['source_rows']) for r in rows),
                        'counts':{k:len(v) for k,v in findings.items()},
                        'review':{k:v for k,v in findings.items() if k!='leading_cue_agrees'}}
    linear = json.loads((investigation/'linear-validation.json').read_text())
    if linear['dataset_manifest_sha256'] != digest(dataset/'manifest.json'):
        raise ValueError('Linear validation used a different dataset.')
    selected = next(e for e in linear['experiments'] if e['C']==linear['selected_C'])
    existing = {'linear':subgroup(splits['validation'],selected['validation_predictions'])}
    for path in sorted(investigation.glob('*/training-report.json')):
        report = json.loads(path.read_text())
        if report['status']!='succeeded': continue
        if report['dataset_manifest_sha256'] != digest(dataset/'manifest.json'):
            raise ValueError('BERT validation used a different dataset.')
        predictions = report['history'][report['best_epoch']-1]['validation_predictions']
        existing[path.parent.name] = subgroup(splits['validation'],predictions)
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from threadpoolctl import threadpool_limits
    transformations = {
        'frozen_v3_control':lambda t:t,
        'cleaning_v4_only':clean_html_to_text,
        'remove_covid_cdc_sentences':lambda t:HEALTH_SENTENCE.sub(' ',t),
        'remove_qualitative_health_severity':lambda t:SEVERITY.sub(' ',t),
        'remove_generic_advice_sentences':lambda t:GENERIC_SENTENCE.sub(' ',t),
    }
    ablations = []
    with threadpool_limits(limits=2):
        for name, transform in transformations.items():
            for noncovid in ([False,True] if name=='frozen_v3_control' else [False]):
                train = [r for r in splits['train'] if not noncovid or not COVID.search(r['text'])]
                if {r['label'] for r in train}!={0,1,2,3}: raise ValueError('Missing training class.')
                train_text = [transform(r['text']) for r in train]
                val_text = [transform(r['text']) for r in splits['validation']]
                empty = {'train':sum(not re.search(r'\w',t) for t in train_text),
                         'validation':sum(not re.search(r'\w',t) for t in val_text)}
                vectorizer = TfidfVectorizer(ngram_range=(1,2),min_df=2,sublinear_tf=True,max_features=20000)
                matrix = vectorizer.fit_transform(train_text)
                model = LogisticRegression(C=linear['selected_C'],class_weight='balanced',max_iter=2000,random_state=42)
                model.fit(matrix,[r['label'] for r in train])
                predictions = [int(v) for v in model.predict(vectorizer.transform(val_text))]
                if name=='frozen_v3_control' and not noncovid and predictions!=selected['validation_predictions']:
                    raise ValueError('Baseline reproduction failed.')
                ablations.append({'name':name+('_noncovid_training_only' if noncovid else ''),
                    'training_rows':len(train), 'training_class_counts':dict(sorted(Counter(r['label']+1 for r in train).items())),
                    'empty_after_intervention':empty,
                    'metrics':metrics([r['label'] for r in splits['validation']],predictions),
                    'subgroups':subgroup(splits['validation'],predictions), 'validation_predictions':predictions})
    result = {'dataset_manifest_sha256':digest(dataset/'manifest.json'), 'label_audit':audit,
              'existing_validation_subgroups':existing,'logistic_ablations':ablations,
              'C_fixed_from_original_validation':linear['selected_C'], 'fresh_predictions_generated':False,
              'limitations':['COVID mention is a lexical subgroup, not a verified publication era or labeling regime.',
                'Leading recommendations screen label consistency but may refer to subregions; disagreements require review.',
                'Ablations are exploratory validation diagnostics; fresh evaluation already consumed and not reused.',
                'Sentence regexes can over-remove content; zero-feature examples and lost risk evidence require review.',
                'Subgroup class distributions differ; macro-F1 averages all four classes even if a subgroup lacks one.']}
    with target.open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')
    print('Audit saved:',target)
    for name, value in existing.items():
        print(name,{k:{'rows':v['rows'],'accuracy':v['metrics']['accuracy'],'macro_f1':v['metrics']['macro_f1']} for k,v in value.items()})
    for row in ablations:
        print(row['name'],round(row['metrics']['accuracy'],4),round(row['metrics']['macro_f1'],4),row['empty_after_intervention'])


if __name__=='__main__':main()
