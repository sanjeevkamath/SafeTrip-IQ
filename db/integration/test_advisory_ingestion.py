"""Real local V2 batch ingestion: idempotence, snapshots, rollback and score isolation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import xml.etree.ElementTree as ET

from safetrip.cli import main
from safetrip.ingestion.multisource import decode_capture, envelope, normalize_bundle
from safetrip.persistence.advisories import ingest_capture
from safetrip.persistence.postgres import PostgresPublisher, ScorePublicationError
from test_local_database import connect

ROOT=Path(__file__).resolve().parents[2]
URL='postgresql+psycopg://safetrip_writer:writer_local_only@127.0.0.1:55432/safetrip'


class AdvisoryIngestionTests(unittest.TestCase):
    def setUp(self):
        self.writer=PostgresPublisher(URL)
        self.prefix='integration-'+uuid.uuid4().hex
        self.run_ids=set()
        self.bundle=json.loads((ROOT/'tests/fixtures/us_uk_capture.json').read_text())
        for index,capture in enumerate(self.bundle['captures']):
            body=decode_capture(capture)
            if capture['source']=='us_state':
                xml=ET.fromstring(body)
                for i,item in enumerate(xml.findall('./channel/item')):item.find('guid').text=self.prefix+'-us-'+str(i)
                body=ET.tostring(xml)
            else:
                obj=json.loads(body)
                if capture['source']=='uk_index':
                    for child in obj['links']['children']:child['content_id']=self.prefix+'-'+child['details']['country']['slug']
                else:obj['content_id']=self.prefix+'-'+obj['details']['country']['slug']
                body=json.dumps(obj).encode()
            self.bundle['captures'][index]=envelope(capture['source'],capture['url'],body,capture['fetched_at'])
        self.keys=[r['source_key'] for r in normalize_bundle(self.bundle)]
        with connect('reader') as conn:self.scores=conn.execute('SELECT * FROM scores ORDER BY iso3').fetchall()

    def ingest(self,bundle=None):
        try:return ingest_capture(self.writer,bundle or self.bundle)
        finally:
            if self.writer.last_run_id:self.run_ids.add(self.writer.last_run_id)

    def tearDown(self):
        self.writer.close()
        # Delete only this test's unique identities using the local admin, never the runtime writer.
        with connect('admin') as conn:
            docs=[r[0] for r in conn.execute('SELECT document_id FROM advisory.documents WHERE source_key=ANY(%s)',(self.keys,))]
            versions=[r[0] for r in conn.execute('SELECT version_id FROM advisory.versions WHERE document_id=ANY(%s)',(docs,))]
            for table in ['evidence','analyses','paragraphs','coverage']:
                conn.execute(f'DELETE FROM advisory.{table} WHERE version_id=ANY(%s)',(versions,))
            conn.execute('DELETE FROM advisory.observations WHERE document_id=ANY(%s)',(docs,))
            conn.execute('DELETE FROM advisory.versions WHERE document_id=ANY(%s)',(docs,))
            conn.execute('DELETE FROM advisory.documents WHERE document_id=ANY(%s)',(docs,))
            for table in ['raw_feeds','pipeline_runs']:
                conn.execute(f'DELETE FROM public.{table} WHERE run_id=ANY(%s)',(list(self.run_ids),))
        with connect('reader') as conn:self.assertEqual(conn.execute('SELECT * FROM scores ORDER BY iso3').fetchall(),self.scores)

    def test_replay_reuses_versions_retains_observations_and_has_no_publication(self):
        first=self.ingest();second=self.ingest()
        self.assertEqual(first['storage']['new_documents'],4)
        self.assertEqual(first['storage']['new_versions'],4)
        self.assertEqual(second['storage']['new_versions'],0)
        self.assertEqual(second['storage']['reused_versions'],4)
        with connect('writer') as conn:
            rows=conn.execute('''SELECT o.fetched_at::date FROM advisory.observations o
                JOIN advisory.documents d USING(document_id) WHERE d.source_key=ANY(%s)''',(self.keys,)).fetchall()
            self.assertEqual(len(rows),8)
            self.assertTrue(all(str(r[0])=='2026-11-03' for r in rows))
            self.assertEqual(conn.execute('SELECT status,published_rows FROM pipeline_runs WHERE run_id=%s',(self.writer.last_run_id,)).fetchone(),('succeeded',0))

    def test_changed_body_creates_one_new_version_without_overwriting_old_evidence(self):
        self.ingest()
        c=self.bundle['captures'][-1];obj=json.loads(decode_capture(c))
        obj['details']['parts'][0]['body']='<h2>Weather</h2><p>New flooding affects transport.</p>'
        self.bundle['captures'][-1]=envelope(c['source'],c['url'],json.dumps(obj).encode(),c['fetched_at'])
        report=self.ingest()
        self.assertEqual(report['storage']['new_versions'],1)
        self.assertEqual(report['storage']['reused_versions'],3)
        with connect('writer') as conn:
            bodies=[r[0] for r in conn.execute('''SELECT p.body FROM advisory.paragraphs p
                JOIN advisory.versions v USING(version_id) JOIN advisory.documents d USING(document_id)
                WHERE d.source_key=%s''',(self.prefix+'-japan',))]
            self.assertIn('Theft occurs in crowded areas.',bodies)
            self.assertIn('New flooding affects transport.',bodies)

    def test_mid_batch_error_rolls_back_every_document_but_keeps_raw_and_failure(self):
        from sqlalchemy import event
        count=0
        def fail(conn,cursor,statement,parameters,context,executemany):
            nonlocal count
            if 'INSERT INTO advisory.observations' in statement:
                count+=1
                if count==2:raise RuntimeError('Simulated second-document failure')
        event.listen(self.writer.engine,'before_cursor_execute',fail)
        try:
            with self.assertRaises(RuntimeError):self.ingest()
        finally:event.remove(self.writer.engine,'before_cursor_execute',fail)
        with connect('writer') as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM advisory.documents WHERE source_key=ANY(%s)',(self.keys,)).fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT status,error_type FROM pipeline_runs WHERE run_id=%s',(self.writer.last_run_id,)).fetchone(),('failed','RuntimeError'))
            self.assertEqual(conn.execute('SELECT count(*) FROM raw_feeds WHERE run_id=%s',(self.writer.last_run_id,)).fetchone()[0],1)

    def test_parser_change_without_version_bump_is_rejected(self):
        self.ingest();rows=normalize_bundle(self.bundle)
        rows[0]['sections'][0]['paragraphs'][0]['text']='Different parser output'
        with patch('safetrip.ingestion.multisource.normalize_bundle',return_value=rows):
            with self.assertRaises(ScorePublicationError):self.ingest()
        with connect('writer') as conn:
            self.assertEqual(conn.execute('SELECT status FROM pipeline_runs WHERE run_id=%s',(self.writer.last_run_id,)).fetchone()[0],'failed')

    def test_real_cli_private_write_does_not_load_bert_or_call_supabase(self):
        with tempfile.TemporaryDirectory() as directory,patch('safetrip.config.load_environment'),patch.dict('os.environ',{
            'SAFETRIP_DB_BACKEND':'postgres','SAFETRIP_DATABASE_URL':URL},clear=True),\
            patch('safetrip.persistence.supabase.get_writer_client') as supabase,patch('safetrip.inference.bert.load_model') as model:
            capture=Path(directory)/'capture.json';capture.write_text(json.dumps(self.bundle))
            output=Path(directory)/'result.json'
            self.assertEqual(main(['ingest-advisories','--input',str(capture),'--output',str(output),'--write']),0)
            report=json.loads(output.read_text());self.run_ids.add(uuid.UUID(report['run_id']))
            self.assertTrue(report['database_written']);self.assertFalse(report['public_scores_changed'])
            self.assertEqual(report['storage']['new_versions'],4)
            supabase.assert_not_called();model.assert_not_called()
