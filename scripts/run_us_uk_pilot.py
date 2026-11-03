"""Collect and normalize a small read-only advisory pilot. No model or DB writes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import time
import xml.etree.ElementTree as ET

from safetrip.ingestion.uk_advisories import normalize_uk, paragraphs
from safetrip.ingestion.countries import resolve_iso3

ROOT = Path(__file__).resolve().parents[1]
DESTINATIONS = {'france':'FRA','thailand':'THA','afghanistan':'AFG','india':'IND','ukraine':'UKR',
                'japan':'JPN','canada':'CAN','mexico':'MEX','kenya':'KEN','nigeria':'NGA',
                'turkey':'TUR','south-africa':'ZAF'}


def main():
    import requests
    root = ROOT/'.local/research/us-uk-pilot-v1'
    root.mkdir(exist_ok=False)
    raw = root/'raw';raw.mkdir()
    documents = []
    response = requests.get('https://travel.state.gov/_res/rss/TAsTWs.xml',timeout=(5,30))
    response.raise_for_status()
    (raw/'us.xml').write_bytes(response.content)
    for number,item in enumerate(ET.fromstring(response.content).findall('./channel/item')):
        title = item.findtext('title','')
        match = re.match(r'^(.+?)\s+[–-]\s+Level\s*([1-4])\b',title)
        if not match: continue
        code = next((c.text for c in item.findall('category') if c.get('domain')=='Country-Tag'),None)
        iso3 = resolve_iso3(match.group(1),code,allow_regions=True)
        if iso3 not in DESTINATIONS.values(): continue
        documents.append({'source':'us_state','source_id':item.findtext('guid') or str(number),
            'iso3':iso3,'covered_iso3':[iso3],'mapping_review_required':False,'country_name':match.group(1),
            'source_url':item.findtext('link'),'source_public_updated_at':item.findtext('pubDate'),
            'official_level':int(match.group(2)), 'sections':[{'slug':'advisory-body','title':'Advisory body',
            'paragraphs':paragraphs(item.findtext('description',''))}]})
    for slug, expected in DESTINATIONS.items():
        cached = ROOT/'.local/research/uk-api'/(slug+'.json')
        if cached.exists():
            content = cached.read_bytes();mode='previous_probe_snapshot'
        else:
            response = requests.get('https://www.gov.uk/api/content/foreign-travel-advice/'+slug,
                                    timeout=(5,30),headers={'Accept':'application/json'})
            response.raise_for_status();content=response.content;mode='new_get'
            time.sleep(1)
        (raw/(slug+'.json')).write_bytes(content)
        doc = normalize_uk(json.loads(content))
        if doc['iso3']!=expected:raise ValueError('Destination mapping disagrees with pilot plan.')
        doc['collection_mode']=mode
        documents.append(doc)
        print('Normalized UK',slug,flush=True)
    for iso in DESTINATIONS.values():
        if not any(d['source']=='us_state' and d['iso3']==iso for d in documents):
            raise ValueError('Missing US pairing for '+iso)
    samples=[]
    generator=random.Random(42)
    for doc in documents:
        candidates=[{'section':s['slug'],**p} for s in doc['sections'] for p in s['paragraphs']
                    if len(p['text'].split())>=8]
        for p in generator.sample(candidates,min(2,len(candidates))):
            samples.append({'id':str(len(samples)+1),'source':doc['source'],'iso3':doc['iso3'],
                'section':p['section'],'heading':p['heading'],'text':p['text']})
    def save(name,value):
        path=root/name;path.write_text(json.dumps(value,indent=2));return hashlib.sha256(path.read_bytes()).hexdigest()
    hashes={'documents.json':save('documents.json',documents),'evaluation-sample.json':save('evaluation-sample.json',samples)}
    report={'prepared_at_utc':datetime.now(timezone.utc).isoformat(),'planned_destinations':DESTINATIONS,
        'documents':len(documents),'sources':{s:sum(d['source']==s for d in documents) for s in ['us_state','uk_fcdo']},
        'paragraphs':sum(len(s['paragraphs']) for d in documents for s in d['sections']),
        'sample_rows':len(samples),'sample_seed':42,'artifacts':hashes,
        'raw_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir()},
        'limitations':['Feasibility pilot, not a new independent model-promotion evaluation set.',
            'US feed may overlap the previously consumed cohort; five UK documents were already inspected.',
            'Pilot documents deliberately selected; paragraph sampling reproducible but small.',
            'Regional and same-date duplicate publication policies are not resolved by this read-only collection.']}
    save('manifest.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
