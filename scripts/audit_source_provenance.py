"""Offline exact lineage checks; never infer a date from a COVID mention or nearest text."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def legacy_normalize(text):
    text = re.sub(r'http\S+|www\S+', '', text.lower())
    text = re.sub(r"[^a-zA-Z\s.,!?:;'-]", '', text)
    return re.sub(r'\s+', ' ', text).strip()


def main():
    output = ROOT/'.local/research/bert/investigation-v3c/source-lineage-audit.json'
    if output.exists(): raise FileExistsError('Preserve existing lineage audit.')
    sources = defaultdict(list)
    inventory = []
    for name in ['old_advisories_minimal_no_merge.csv','old_advisories_minimal_pt2.csv']:
        path = ROOT/'research/bert/wayback'/name
        rows = list(csv.DictReader(path.open()))
        inventory.append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                          'rows':len(rows),'label_counts':dict(Counter(r['label'] for r in rows))})
        for index,row in enumerate(rows,2):
            sources[legacy_normalize(row['text_advisory'])].append({'file':name,'row':index,'level':int(row['label']),
                                                                   'country':None,'publication_date':None})
    path = ROOT/'research/bert/wayback/old_advisories.minimal.csv'
    blocks = re.split(r'### ITEM \d+ ###',path.read_text())
    capture_rows = 0
    for block in blocks[1:]:
        match = re.match(r'\s*TITLE: (.+?)\n\s*\n(.*)',block,re.S)
        if not match: continue
        title,body = match.groups()
        body = body.split('='*80)[0].strip()
        level = re.search(r'\s+[–-]\s+Level\s*([1-4])\b',title)
        if not level: continue
        capture_rows += 1
        sources[legacy_normalize(body)].append({'file':path.name,'level':int(level.group(1)),
            'country':title[:level.start()].strip(),'publication_date':None})
    matches = []
    totals = Counter()
    for split in ['train','test']:
        path = ROOT/f'data/baseline/bert/{split}.csv'
        for index,row in enumerate(csv.DictReader(path.open()),2):
            found = sources.get(legacy_normalize(row['text']),[])
            if found:
                totals['matched_source_rows'] += 1
                if any(int(row['label'])!=r['level'] for r in found): totals['rows_with_label_disagreement'] += 1
                matches.append({'source_split':split,'source_row':index,'stored_level':int(row['label']),
                                'matches':found})
    report = {'method':'Exact equality after the documented legacy JSON-to-CSV normalization; not fuzzy matching.',
        'inventory':inventory,'raw_capture_labeled_items':capture_rows,'counts':dict(totals),
        'matches':matches,'publication_dates_recovered':0,
        'limitations':['Repository CSVs and text captures lack per-row publication timestamps.',
            'Matching an intermediate file establishes text lineage, not a verified government publication date.',
            'Wayback timestamps in script configuration identify possible fetch snapshots, not the dates of individual CSV rows.',
            'The legacy JSON converter removes digits, damaging numeric risk evidence and dates.',
            'The archived export helper excludes all Level 1 bodies beginning with Exercise normal precautions; whether it generated a particular CSV must be established separately.']}
    with output.open('x') as stream: json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='matches'},indent=2))


if __name__=='__main__':main()
