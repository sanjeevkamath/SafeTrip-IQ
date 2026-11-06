"""Evaluate the cheap topic baseline on a developer-reviewed feasibility sample."""
import hashlib
import json
from pathlib import Path
import time
from collections import Counter
from research.advisory_nlp.risk_evidence import extract_topics, PATTERNS

ROOT=Path(__file__).resolve().parents[2]


def main():
    root=ROOT/'.local/research/us-uk-pilot-v1'
    output=root/'evaluation.json'
    if output.exists():raise FileExistsError('Keep the original pilot evaluation.')
    samples=json.loads((root/'evaluation-sample.json').read_text())
    annotations=json.loads((root/'topic-annotations.json').read_text())
    if hashlib.sha256((root/'evaluation-sample.json').read_bytes()).hexdigest()!=annotations['sample_sha256']:
        raise ValueError('Annotated sample changed.')
    if set(annotations['labels'])!={r['id'] for r in samples}:raise ValueError('Annotations do not cover sample.')
    started=time.perf_counter()
    predictions=[extract_topics(r['text'],r['heading']) for r in samples]
    elapsed=time.perf_counter()-started
    reports={}
    errors=[]
    for source in ['all','us_state','uk_fcdo']:
        indices=[i for i,r in enumerate(samples) if source=='all' or r['source']==source]
        stats={}
        totals=Counter()
        exact=0
        for category in PATTERNS:
            count=Counter()
            for i in indices:
                gold=category in annotations['labels'][samples[i]['id']]
                predicted=category in predictions[i]['topics']
                count['tp']+=gold and predicted;count['fp']+=not gold and predicted;count['fn']+=gold and not predicted
            totals.update(count)
            precision=count['tp']/(count['tp']+count['fp']) if count['tp']+count['fp'] else None
            recall=count['tp']/(count['tp']+count['fn']) if count['tp']+count['fn'] else None
            stats[category]={**count,'precision':precision,'recall':recall}
        for i in indices:exact+=set(predictions[i]['topics'])==set(annotations['labels'][samples[i]['id']])
        reports[source]={'paragraphs':len(indices),'exact_topic_set_accuracy':exact/len(indices),
            'micro_precision':totals['tp']/(totals['tp']+totals['fp']),
            'micro_recall':totals['tp']/(totals['tp']+totals['fn']),'per_category':stats}
    for row,prediction in zip(samples,predictions):
        gold=annotations['labels'][row['id']]
        if set(gold)!=set(prediction['topics']):
            errors.append({**row,'gold':gold,'predicted':prediction['topics']})
    documents=json.loads((root/'documents.json').read_text())
    evidence=[]
    for doc in documents:
        for section in doc['sections']:
            for number,p in enumerate(section['paragraphs']):
                result=extract_topics(p['text'],p['heading'])
                if result['topics']:
                    evidence.append({'source':doc['source'],'iso3':doc['iso3'],'source_id':doc['source_id'],
                        'source_url':doc['source_url'],'section':section['slug'],'paragraph_index':number,**result})
    report={'annotation_sha256':hashlib.sha256((root/'topic-annotations.json').read_bytes()).hexdigest(),
        'baseline_source_sha256':hashlib.sha256((ROOT/'research/advisory_nlp/risk_evidence.py').read_bytes()).hexdigest(),
        'sample_seconds':elapsed,'metrics':reports,'errors':errors,'evidence_paragraphs':len(evidence),
        'limitations':annotations['rubric']['limitations'], 'combined_score_validated':False}
    output.write_text(json.dumps(report,indent=2))
    (root/'evidence.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['errors','metrics']},indent=2))
    for k,v in reports.items():print(k,{key:value for key,value in v.items() if key!='per_category'})
    print('Errors:',len(errors))


if __name__=='__main__':main()
