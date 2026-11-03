import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from safetrip.cli import main
from safetrip.ingestion.multisource import (
    capture_bundle, decode_capture, envelope, normalize_bundle, official_url, timestamp, preview,
)

FIXTURE = Path(__file__).parent/'fixtures/us_uk_capture.json'


class MultisourceIngestionTests(unittest.TestCase):
    def bundle(self):
        return json.loads(FIXTURE.read_text())

    def test_both_sources_join_by_country_and_preserve_independent_warnings(self):
        rows=normalize_bundle(self.bundle())
        self.assertEqual(len(rows),4)
        us=[r for r in rows if r['source']=='us_state']
        self.assertEqual([r['us_level'] for r in us],[1,1])
        uk=[r for r in rows if r['source']=='uk_fcdo']
        self.assertEqual(uk[1]['uk_alert_status'],['avoid_all_but_essential_travel_to_parts'])
        self.assertTrue(all(s['slug']!='entry-requirements' for r in uk for s in r['sections']))
        self.assertEqual({c['iso3'] for r in rows for c in r['coverage']},{'CAN','JPN'})

    def test_partial_capture_corruption_missing_source_and_duplicate_document_rejected(self):
        cases=[]
        b=self.bundle();b['complete']=False;cases.append(b)
        b=self.bundle();b['captures'][0]['sha256']='0'*64;cases.append(b)
        b=self.bundle();b['captures'].pop();cases.append(b)
        b=self.bundle();b['captures'].append(copy.deepcopy(b['captures'][-1]));cases.append(b)
        for bundle in cases:
            with self.subTest(),self.assertRaises(ValueError):normalize_bundle(bundle)

    def test_source_identity_and_unknown_flags_cannot_be_substituted(self):
        for change in [lambda d:d.update(content_id='wrong-id'),
                       lambda d:d['details'].update(alert_status=['new-unknown-flag'])]:
            b=self.bundle();c=b['captures'][-1];data=json.loads(decode_capture(c));change(data)
            b['captures'][-1]=envelope(c['source'],c['url'],json.dumps(data).encode(),c['fetched_at'])
            with self.assertRaises(ValueError):normalize_bundle(b)

    def test_destination_with_one_source_is_valid_and_missing_source_is_explicit(self):
        from xml.etree import ElementTree as ET
        b=self.bundle();b['iso3']=['CAN']
        c=b['captures'][1];xml=ET.fromstring(decode_capture(c));channel=xml.find('channel');channel.remove(channel.find('item'))
        b['captures'][1]=envelope(c['source'],c['url'],ET.tostring(xml),c['fetched_at'])
        b['captures'].pop()  # Only the selected UK Canada document is expected.
        rows=normalize_bundle(b)
        self.assertEqual(len(rows),1)
        report=preview(rows,requested=['CAN'])
        self.assertEqual(report['coverage_by_country']['CAN']['us_state']['status'],'not_in_capture')
        self.assertEqual(report['coverage_by_country']['CAN']['uk_fcdo']['status'],'available')
        self.assertFalse(report['public_scores_changed'])

    def test_distinct_documents_for_one_country_are_kept_and_flagged(self):
        b=self.bundle();c=next(c for c in b['captures'] if c['source']=='us_state')
        from xml.etree import ElementTree as ET
        xml=ET.fromstring(decode_capture(c));item=copy.deepcopy(xml.find('./channel/item'))
        item.find('guid').text='another-canada-advisory'
        xml.find('channel').append(item)
        b['captures'][b['captures'].index(c)]=envelope(c['source'],c['url'],ET.tostring(xml),c['fetched_at'])
        report=preview(normalize_bundle(b))
        self.assertEqual(report['sources']['us_state'],3)
        self.assertEqual(report['review_required'],2)
        self.assertEqual(report['overlapping_country_documents'][0]['iso3'],'CAN')

    def test_compound_uk_destination_is_stored_as_unresolved_not_one_country(self):
        b=self.bundle();b['iso3']=None
        index_capture=b['captures'][0];index=json.loads(decode_capture(index_capture))
        child=index['links']['children'][0]
        child['base_path']='/foreign-travel-advice/st-martin-and-st-barthelemy'
        child['details']['country']={'name':'St Martin and St Barthélemy','slug':'st-martin-and-st-barthelemy'}
        b['captures'][0]=envelope(index_capture['source'],index_capture['url'],json.dumps(index).encode(),index_capture['fetched_at'])
        c=b['captures'][2];obj=json.loads(decode_capture(c));obj['base_path']=child['base_path']
        obj['details']['country']=child['details']['country']
        b['captures'][2]=envelope(c['source'],'https://www.gov.uk/api/content'+child['base_path'],json.dumps(obj).encode(),c['fetched_at'])
        rows=normalize_bundle(b);compound=next(r for r in rows if r['country_name']=='St Martin and St Barthélemy')
        self.assertEqual(compound['coverage'][0]['scope'],'unresolved')
        self.assertIsNone(compound['coverage'][0]['iso3'])
        self.assertEqual(compound['metadata']['covered_iso3_candidates'],['MAF','BLM'])
        self.assertEqual(preview(rows)['review_required'],1)

    def test_date_only_dates_are_preserved_as_utc_and_naive_time_rejected(self):
        self.assertEqual(timestamp('Sun, 01 Nov 2026'),'2026-11-01T00:00:00+00:00')
        with self.assertRaises(ValueError):timestamp('2026-11-01T12:00:00')

    def test_capture_urls_must_stay_on_the_official_source(self):
        for url in ['http://www.gov.uk/foreign-travel-advice','https://www.gov.uk.evil.test/x',
                    'https://user:secret@www.gov.uk/x','https://www.gov.uk/x?token=example']:
            with self.assertRaises(ValueError):official_url(url,'uk_fcdo')

    def test_capture_retains_partial_bytes_on_http_failure(self):
        bundle=self.bundle();responses={c['url']:decode_capture(c) for c in bundle['captures']}
        calls=[]
        def fetch(url):
            calls.append(url)
            if len(calls)==3:raise RuntimeError('simulated HTTP failure')
            return responses[url]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'capture.json'
            with self.assertRaises(RuntimeError):capture_bundle(path,['CAN','JPN'],fetch=fetch,pause=lambda _:None)
            partial=json.loads(path.read_text())
            self.assertFalse(partial['complete']);self.assertEqual(len(partial['captures']),2)
            with self.assertRaises(ValueError):normalize_bundle(partial)

    def test_container_entrypoint_skips_model_bootstrap_for_source_ingestion(self):
        from safetrip.cloud_entrypoint import main as entrypoint
        for command in ['capture-advisories','ingest-advisories']:
            with patch('sys.argv',['worker',command,'--help']),patch('os.execvp') as execute,\
                 patch('safetrip.inference.s3_checkpoint.bootstrap_from_environment') as bootstrap:
                self.assertEqual(entrypoint(),0)
                bootstrap.assert_not_called()
                execute.assert_called_once_with('safetrip',['safetrip',command,'--help'])

    def test_capture_and_preview_are_model_and_database_free(self):
        bundle=self.bundle();responses={c['url']:decode_capture(c) for c in bundle['captures']}
        with tempfile.TemporaryDirectory() as directory,patch('safetrip.persistence.publication.get_publisher') as db,patch('safetrip.inference.bert.load_model') as model:
            capture=Path(directory)/'capture.json'
            capture_bundle(capture,['CAN','JPN'],fetch=responses.__getitem__,pause=lambda _:None)
            output=Path(directory)/'preview.json'
            self.assertEqual(main(['ingest-advisories','--input',str(capture),'--output',str(output)]),0)
            report=json.loads(output.read_text())
            self.assertFalse(report['database_written']);self.assertFalse(report['public_scores_changed'])
            self.assertEqual(report['sources'],{'us_state':2,'uk_fcdo':2})
            self.assertEqual(main(['ingest-advisories','--input',str(capture),'--output',str(output),'--write']),1)
            db.assert_not_called();model.assert_not_called()
