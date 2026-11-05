"""Real scoped publication, provenance, stale-plan rejection and rollback."""
import json
import unittest
from sqlalchemy import text,event
from sqlalchemy.exc import DBAPIError
import psycopg
from psycopg import sql
from safetrip.persistence.official_scores import OfficialScorePublisher
from safetrip.persistence.postgres import ScorePublicationError
from safetrip.scoring.snapshot import COUNTRIES_SQL,PUBLISHED_SQL,ADVISORIES_SQL,snapshot_hash,calculate
from test_local_database import connect

URL='postgresql+psycopg://safetrip_score_publisher:publisher_local_only@127.0.0.1:55432/safetrip'
FIELDS=['safe_trip_score','official_us_level','official_us_component','clustering_component',
        'scoring_version','score_run_id','score_published_at']


class OfficialScoreTests(unittest.TestCase):
    def setUp(self):
        with connect('admin') as c:
            c.execute("ALTER ROLE safetrip_score_publisher LOGIN PASSWORD 'publisher_local_only'")
            self.original=c.execute('SELECT iso3,'+','.join(FIELDS)+',bert_score,clustering_score FROM public.scores ORDER BY iso3').fetchall()
        self.publisher=OfficialScorePublisher(URL)
        self.runs=[]

    def tearDown(self):
        self.publisher.close()
        with connect('admin') as c:
            for row in self.original:
                c.execute(sql.SQL('UPDATE public.scores SET {} WHERE iso3=%s').format(
                    sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(f)) for f in FIELDS)),(*row[1:1+len(FIELDS)],row[0]))
            for run in self.runs:
                c.execute('DELETE FROM public.official_score_history WHERE run_id=%s',(run,))
                c.execute('DELETE FROM public.pipeline_runs WHERE run_id=%s',(run,))
            c.execute('ALTER ROLE safetrip_score_publisher NOLOGIN')

    def plan(self):
        with self.publisher.engine.connect() as c:
            snapshot={key:[dict(row) for row in c.execute(text(query)).mappings()] for key,query in [
                ('countries',COUNTRIES_SQL),('published_scores',PUBLISHED_SQL),('official_us_advisories',ADVISORIES_SQL)]}
        artifact=calculate(snapshot)
        # Round-trip just as a saved preview is loaded by the operator CLI.
        return json.loads(json.dumps({'database_written':False,'input_sha256':snapshot_hash(snapshot),
                                      'previews':{'exclude':artifact}},default=str))

    def publish(self,plan):
        try:return self.publisher.publish(plan)
        finally:
            if self.publisher.history.last:self.runs.append(self.publisher.history.last)

    def test_success_keeps_model_inputs_and_saves_versioned_source_history(self):
        plan=self.plan();result=self.publish(plan)
        self.assertEqual(result['published_rows'],3)
        with connect('reader') as c:
            rows=c.execute('SELECT iso3,bert_score,clustering_score,official_us_level,scoring_version FROM public.scores ORDER BY iso3').fetchall()
            self.assertEqual([(r[0],r[1],r[2]) for r in rows],[(r[0],r[-2],r[-1]) for r in self.original])
            self.assertTrue(all(r[4]=='us-official-cluster-v1' for r in rows))
            self.assertEqual(next(r[3] for r in rows if r[0]=='USA'),None)
        with self.publisher.engine.connect() as c:
            stored=c.execute(text('SELECT inputs FROM public.official_score_history WHERE run_id=:run'),{'run':result['run_id']}).scalars().all()
            self.assertEqual(len(stored),3)
            self.assertTrue(all(r['official_us_level'] is None or r['source_advisories'] for r in stored))
        with self.assertRaises(ScorePublicationError):self.publish(plan)

    def test_changed_inputs_or_tampered_results_are_rejected_without_score_writes(self):
        for change in ['input','result']:
            plan=self.plan()
            if change=='input':plan['input_sha256']='0'*64
            else:plan['previews']['exclude']['scores'][0]['safe_trip_score']=123
            with self.assertRaises(ScorePublicationError):self.publish(plan)
        with connect('reader') as c:
            self.assertEqual(c.execute('SELECT iso3,'+','.join(FIELDS)+',bert_score,clustering_score FROM public.scores ORDER BY iso3').fetchall(),self.original)
        with self.publisher.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM public.pipeline_runs WHERE run_id=ANY(:runs) AND status='failed'"),{'runs':self.runs}).scalar_one(),2)

    def test_mid_publication_failure_rolls_back_history_and_every_score(self):
        count=0
        def fail(conn,cursor,statement,params,context,executemany):
            nonlocal count
            if 'INSERT INTO public.scores' in statement:
                count+=1
                if count==2:raise RuntimeError('Synthetic failure')
        event.listen(self.publisher.engine,'before_cursor_execute',fail)
        try:
            with self.assertRaises(RuntimeError):self.publish(self.plan())
        finally:event.remove(self.publisher.engine,'before_cursor_execute',fail)
        with connect('reader') as c:
            self.assertEqual(c.execute('SELECT iso3,'+','.join(FIELDS)+',bert_score,clustering_score FROM public.scores ORDER BY iso3').fetchall(),self.original)
        with self.publisher.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT count(*) FROM public.official_score_history WHERE run_id=:run'),{'run':self.runs[-1]}).scalar_one(),0)

    def test_real_source_change_after_preview_is_not_overwritten(self):
        plan=self.plan()
        with connect('admin') as c:c.execute("UPDATE public.scores SET safe_trip_score=9 WHERE iso3='CAN'")
        with self.assertRaises(ScorePublicationError):self.publish(plan)
        with connect('reader') as c:
            self.assertEqual(c.execute("SELECT safe_trip_score FROM public.scores WHERE iso3='CAN'").fetchone()[0],9)

    def test_role_cannot_modify_predictions_tiers_raw_advisories_or_erase_scores(self):
        statements=["UPDATE public.scores SET bert_score=0 WHERE false",'UPDATE public.scores SET clustering_score=0 WHERE false',
                    'DELETE FROM public.scores WHERE false','TRUNCATE public.scores','SELECT * FROM advisory.versions',
                    "UPDATE public.pipeline_runs SET status='failed',finished_at=now() WHERE command <> 'publish-official-scores'"]
        with self.publisher.engine.connect() as c:
            for statement in statements[:-1]:
                with self.subTest(statement=statement):
                    transaction=c.begin()
                    try:
                        with self.assertRaises(DBAPIError) as error:c.execute(text(statement))
                        self.assertIsInstance(error.exception.orig,psycopg.errors.InsufficientPrivilege)
                    finally:transaction.rollback()
            self.assertEqual(c.execute(text(statements[-1])).rowcount,0)
            c.rollback()
