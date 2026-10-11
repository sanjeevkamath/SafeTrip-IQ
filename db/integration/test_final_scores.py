"""Final-score publication against a disposable local database, never Supabase."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from psycopg import sql
from safetrip.cli import main
from safetrip.persistence.postgres import PostgresPublisher, PUBLICATION_LOCK
from test_local_database import connect

ROOT = Path(__file__).resolve().parents[2]


class FinalScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = "safetrip_scores_" + uuid.uuid4().hex[:12]
        with connect("admin", autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER safetrip_migrator").format(sql.Identifier(cls.database)))
        cls.addClassCleanup(cls.drop_database)
        migration_url = f"postgresql+psycopg://safetrip_migrator:migrator_local_only@127.0.0.1:55432/{cls.database}"
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT,
                       env=dict(os.environ, SAFETRIP_MIGRATION_URL=migration_url), check=True, capture_output=True)
        with connect("migrator", cls.database) as conn:
            conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            conn.execute("GRANT USAGE ON SCHEMA public TO safetrip_reader, safetrip_writer")
        cls.url = f"postgresql+psycopg://safetrip_writer:writer_local_only@127.0.0.1:55432/{cls.database}"

    @classmethod
    def drop_database(cls):
        with connect("admin", autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cls.database)))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "scores.json"
        self.writer = PostgresPublisher(self.url)
        self.addCleanup(self.writer.close)
        with connect("admin", self.database) as conn:
            conn.execute("TRUNCATE public.countries, public.scores, public.travel_advisories CASCADE")
        with connect("writer", self.database) as conn:
            conn.execute("INSERT INTO countries (iso3,name) VALUES ('AAA','Both'),('BBB','BERT only'),('CCC','Cluster only'),('DDD','Neither')")
            conn.execute("INSERT INTO bert_scores (iso3,bert_score) VALUES ('AAA',0),('BBB',3)")
            conn.execute("INSERT INTO clustering (iso3,clustering_score,score_kind) VALUES ('AAA',0,'risk_tier'),('CCC',2,'risk_tier')")
            # Deliberately stale value must become NULL when no components exist.
            conn.execute("INSERT INTO scores (iso3,safe_trip_score) VALUES ('DDD',9)")

    def scores(self):
        with connect("reader", self.database) as conn:
            return conn.execute("SELECT iso3,safe_trip_score,bert_score,clustering_score FROM scores ORDER BY iso3").fetchall()

    def test_baseline_import_is_atomic_and_refuses_existing_data(self):
        from safetrip.persistence.baseline import TABLES
        tables = {table:[] for table in TABLES}
        tables.update(countries=[{'iso3':'AAA','name':'Imported'},{'iso3':'BBB','name':'No score'}],
                      culture=[{'iso3':'AAA','overview':'Captured culture'}],
                      bert_scores=[{'iso3':'AAA','bert_score':0}],
                      clustering=[{'iso3':'AAA','clustering_score':0}],
                      scores=[{'iso3':'AAA','bert_score':0,'clustering_score':0,'safe_trip_score':10}])
        with self.assertRaisesRegex(ValueError, 'empty application tables'):
            self.writer.import_baseline(tables, {'source_kind':'legacy_snapshot'})
        with connect('admin', self.database) as conn:
            conn.execute('TRUNCATE countries,scores,travel_advisories,refresh_status CASCADE')
        with patch.object(self.writer, '_write_final_scores', side_effect=RuntimeError('fail')):
            with self.assertRaises(RuntimeError): self.writer.import_baseline(tables, {})
        with connect('reader', self.database) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM countries').fetchone()[0], 0)
        coverage = self.writer.import_baseline(tables, {'source_kind':'legacy_snapshot'})
        self.assertEqual(coverage, dict(both=1,bert_only=0,clustering_only=0,neither=1))
        self.assertEqual(self.scores(), [('AAA',10,0,0),('BBB',None,None,None)])
        self.assertIsNone(self.writer.refresh_status()['last_publication'])

    def test_freshness_advances_only_on_committed_refresh_and_reports_overdue_runs(self):
        with connect("writer", self.database) as conn:
            conn.execute("DELETE FROM refresh_status")
        self.assertIsNone(self.writer.refresh_status()["last_publication"])
        artifact = {"advisories":[{"iso3":"AAA","description_text":"current"}],
                    "bert_scores":[{"iso3":"AAA","bert_score":0}]}
        self.writer.publish("refresh", artifact, publish_scores=True, metadata={"source_kind":"local_xml"})
        status = self.writer.refresh_status()["last_publication"]
        self.assertEqual(status["source_kind"], "local_xml")
        self.assertFalse(status["overdue"])
        with patch.object(self.writer.history, "succeeded", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                self.writer.publish("refresh", artifact, publish_scores=True)
        self.assertEqual(self.writer.refresh_status()["last_publication"], status)
        self.writer.publish_scores(self.output, write=True)
        self.assertEqual(self.writer.refresh_status()["last_publication"], status)
        with connect("writer", self.database) as conn:
            conn.execute("UPDATE refresh_status SET published_at=now()-interval '49 hours'")
            old_id = uuid.uuid4()
            conn.execute("INSERT INTO pipeline_runs (run_id,command,status,started_at) VALUES (%s,'refresh','running',now()-interval '2 hours')", (old_id,))
        report = self.writer.refresh_status()
        self.assertTrue(report["last_publication"]["overdue"])
        self.assertIn(str(old_id), [r["run_id"] for r in report["overdue_running_attempts"]])
        with connect("reader", self.database) as conn:
            self.assertEqual(conn.execute("SELECT source_kind FROM refresh_status").fetchone(), ("local_xml",))
            with self.assertRaises(Exception):
                conn.execute("UPDATE refresh_status SET published_at=now()")

    def test_incremental_refresh_preserves_prediction_origin_and_rejects_changed_cache(self):
        from safetrip import jobs
        metadata = {"cleaning_version":"legacy-advisory-v1"}
        rows = [{"iso3":"AAA", "description_text":"unchanged"}]
        versions = {**metadata, "model_version":"fingerprint", "inference_version":"bert-cpu-max256-v1"}
        self.writer.publish("score", [{"iso3":"AAA", "cleaned_text":"unchanged", "bert_score":0}], metadata=versions)
        origin = str(self.writer.last_run_id)
        with patch("safetrip.inference.integrity.model_fingerprint", return_value="fingerprint"), \
             patch("safetrip.jobs.score") as inference:
            predictions, reused = jobs.incremental_score(rows, "model", self.writer, metadata)
            inference.assert_not_called()
        artifact = {"advisories":rows, "bert_scores":predictions, "reused_bert_scores":reused}
        self.writer.publish("refresh", artifact, publish_scores=True, metadata=metadata)
        self.assertEqual(self.writer.cached_predictions()["AAA"]["last_run_id"], origin)
        with connect("writer", self.database) as conn:
            recorded = conn.execute("SELECT inputs FROM score_history WHERE run_id=%s AND iso3='AAA'",
                                    (self.writer.last_run_id,)).fetchone()[0]
            self.assertEqual(recorded["bert_input"]["last_run_id"], origin)
            conn.execute("UPDATE bert_scores SET bert_score=1 WHERE iso3='AAA'")
        before = self.scores()
        with self.assertRaisesRegex(ValueError, "reused prediction changed"):
            self.writer.publish("refresh", artifact, publish_scores=True, metadata=metadata)
        self.assertEqual(self.scores(), before)

    def test_raw_feed_survives_parse_failure_and_is_private_append_only(self):
        from hashlib import sha256
        path = self.output.with_suffix(".xml")
        content = b"<rss>malformed\r\n"
        path.write_bytes(content)
        with patch("safetrip.config.load_environment"), patch.dict(os.environ, {
                "SAFETRIP_DB_BACKEND":"postgres", "SAFETRIP_DATABASE_URL":self.url}):
            self.assertEqual(main(["refresh", "--input", str(path), "--output", str(self.output), "--write"]), 1)
        self.assertEqual(Path(str(self.output) + ".source.xml").read_bytes(), content)
        with connect("writer", self.database) as conn:
            raw = conn.execute("SELECT content,sha256,status FROM raw_feeds JOIN pipeline_runs USING(run_id) ORDER BY fetched_at DESC LIMIT 1").fetchone()
            self.assertEqual(raw, (content,sha256(content).hexdigest(),"failed"))
        for role, statement in (("reader","SELECT * FROM raw_feeds"),
                                ("writer","DELETE FROM raw_feeds WHERE false"),
                                ("writer","UPDATE raw_feeds SET sha256=sha256 WHERE false")):
            with connect(role, self.database) as conn:
                with self.assertRaises(Exception):
                    conn.execute(statement)

    def test_preview_is_read_only_and_write_handles_every_missingness_case(self):
        before = self.scores()
        preview = self.writer.publish_scores(self.output)
        self.assertEqual(preview["coverage"], {"both": 1, "bert_only": 1, "clustering_only": 1, "neither": 1})
        self.assertEqual(self.scores(), before)
        self.writer.publish_scores(self.output.with_name("committed.json"), write=True)
        self.assertEqual(self.scores(), [("AAA",10,0,0),("BBB",2.5,3,None),("CCC",6,None,2),("DDD",None,None,None)])
        self.writer.publish_scores(self.output.with_name("again.json"), write=True)
        self.assertEqual(len(self.scores()), 4)
        self.assertEqual(self.scores()[1], ("BBB",2.5,3,None))

    def test_all_212_captured_scores_publish_identically(self):
        fixture = json.loads((ROOT / "tests/fixtures/legacy_scores.json").read_text())["rows"]
        with connect("admin", self.database) as conn:
            conn.execute("TRUNCATE countries, scores CASCADE")
        with self.writer.engine.begin() as conn:
            self.writer._upsert(conn, "countries", [{"iso3":r["iso3"], "name":r["iso3"]} for r in fixture])
            self.writer._upsert(conn, "bert_scores", [{"iso3":r["iso3"], "bert_score":r["bert_score"]} for r in fixture if r["bert_score"] is not None])
            self.writer._upsert(conn, "clustering", [{"iso3":r["iso3"], "clustering_score":r["clustering_score"], "score_kind":"risk_tier"} for r in fixture if r["clustering_score"] is not None])
        artifact = self.writer.publish_scores(self.output, write=True)
        self.assertEqual(artifact["coverage"], {"both":164,"bert_only":44,"clustering_only":4,"neither":0})
        self.assertEqual(self.scores(), sorted((r["iso3"],r["safe_trip_score"],r["bert_score"],r["clustering_score"]) for r in fixture))

    def test_refresh_commits_components_and_final_scores_together(self):
        self.writer.publish("refresh", {"advisories":[{"iso3":"AAA","description_text":"Synthetic update"}],
            "bert_scores":[{"iso3":"AAA","bert_score":3}]}, publish_scores=True)
        self.assertEqual(self.scores()[0], ("AAA",6.25,3,0))
        self.assertEqual(self.scores()[2], ("CCC",6,None,2))

    def test_missing_advisories_become_blank_without_erasing_clustering_or_history(self):
        self.writer.publish_scores(self.output, write=True)
        old_run = self.writer.last_run_id
        with connect("writer", self.database) as conn:
            conn.execute("INSERT INTO travel_advisories (iso3,description_text) VALUES ('AAA','old A'),('BBB','old B')")
        # Only CCC remains in the new complete feed. AAA still has clustering;
        # BBB has no remaining component and must become NULL, never zero.
        artifact = {"advisories":[{"iso3":"CCC","description_text":"Current C"}],
                    "bert_scores":[{"iso3":"CCC","bert_score":1,"cleaned_text":"Current C"}]}
        self.writer.publish("refresh", artifact, publish_scores=True)
        self.assertEqual(self.scores(), [("AAA",10,None,0),("BBB",None,None,None),
                                        ("CCC",6.75,1,2),("DDD",None,None,None)])
        with connect("writer", self.database) as conn:
            self.assertEqual(conn.execute("SELECT iso3 FROM travel_advisories").fetchall(), [("CCC",)])
            self.assertEqual(conn.execute("SELECT iso3 FROM bert_scores").fetchall(), [("CCC",)])
            self.assertEqual(conn.execute("SELECT count(*) FROM clustering").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT bert_score FROM score_history WHERE run_id=%s AND iso3='BBB'", (old_run,)).fetchone()[0], 3)
        metadata = self.writer.recent_runs()[0]["metadata"]
        self.assertEqual(metadata["missing_advisory_iso3"], ["AAA","BBB","DDD"])
        self.assertEqual(metadata["cleared_rows"], {"travel_advisories":2,"bert_scores":2})

    def test_invalid_complete_feed_preserves_existing_data(self):
        before = self.scores()
        row = {"iso3":"AAA", "description_text":"valid text"}
        for artifact in ({"advisories":[],"bert_scores":[]},
                         {"advisories":[row],"bert_scores":[]},
                         {"advisories":[row,row],"bert_scores":[{"iso3":"AAA","bert_score":0}]},
                         {"advisories":[row],"bert_scores":[{"iso3":"BBB","bert_score":0}]}):
            with self.subTest(artifact=artifact), self.assertRaises(ValueError):
                self.writer.publish("refresh", artifact, publish_scores=True)
            self.assertEqual(self.scores(), before)
            self.assertEqual(set(self.writer.cached_predictions()), {"AAA","BBB"})

    def test_refresh_lock_blocks_work_and_releases_after_failure_and_close(self):
        other = PostgresPublisher(self.url)
        self.addCleanup(other.close)
        self.writer.start_run("refresh")
        with patch("safetrip.config.load_environment"), patch.dict(os.environ, {
                "SAFETRIP_DB_BACKEND":"postgres", "SAFETRIP_DATABASE_URL":self.url}), \
             patch("safetrip.jobs.ingest") as ingest:
            self.assertEqual(main(["refresh","--input","unused.xml","--output",str(self.output),"--write"]), 1)
            ingest.assert_not_called()
        with self.assertRaisesRegex(ValueError, "refresh is in progress"):
            other.publish("score", [{"iso3":"AAA","bert_score":2}])
        self.writer.fail_run(ValueError("synthetic failure"))
        other.start_run("refresh")
        other.close()
        # Closing the actual session releases the lock even with a running receipt.
        self.writer.start_run("refresh")
        self.writer.publish("refresh", {"advisories":[{"iso3":"AAA","description_text":"ok"}],
            "bert_scores":[{"iso3":"AAA","bert_score":0}]}, publish_scores=True)
        third = PostgresPublisher(self.url)
        self.addCleanup(third.close)
        third.start_run("refresh")
        third.fail_run(ValueError("cleanup"))

    def test_failure_after_first_final_write_rolls_everything_back(self):
        before = self.scores()
        original = self.writer._upsert
        def fail(conn, table, rows):
            if table == "scores":
                original(conn, table, rows[:1])
                raise RuntimeError("Injected failure during final publication")
            original(conn, table, rows)
        with patch.object(self.writer, "_upsert", side_effect=fail), self.assertRaises(RuntimeError):
            self.writer.publish("refresh", {"advisories":[{"iso3":"AAA","description_text":"Must roll back"}],
                "bert_scores":[{"iso3":"AAA","bert_score":3}]}, publish_scores=True)
        self.assertEqual(self.scores(), before)
        with connect("writer", self.database) as conn:
            self.assertEqual(conn.execute("SELECT bert_score FROM bert_scores WHERE iso3='AAA'").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT bert_score FROM bert_scores WHERE iso3='BBB'").fetchone()[0], 3)
            self.assertEqual(conn.execute("SELECT count(*) FROM travel_advisories").fetchone()[0], 0)
            run_id = self.writer.last_run_id
            self.assertEqual(conn.execute("SELECT status,error_type FROM pipeline_runs WHERE run_id=%s", (run_id,)).fetchone(), ("failed","RuntimeError"))
            self.assertEqual(conn.execute("SELECT count(*) FROM score_history WHERE run_id=%s", (run_id,)).fetchone()[0], 0)

    def test_invalid_component_rolls_back_score_update(self):
        with self.assertRaises(ValueError):
            self.writer.publish("score", [{"iso3":"AAA","bert_score":4}], publish_scores=True)
        with connect("writer", self.database) as conn:
            self.assertEqual(conn.execute("SELECT bert_score FROM bert_scores WHERE iso3='AAA'").fetchone()[0], 0)

    def test_raw_or_unverified_cluster_ids_block_publication(self):
        self.writer.publish("import-clusters", [{"iso3":"AAA","clustering_score":2,"score_kind":"risk_tier"}])
        with connect("writer", self.database) as conn:
            self.assertEqual(conn.execute("SELECT score_kind FROM clustering WHERE iso3='AAA'").fetchone()[0], "raw_cluster_id")
        for kind in ("raw_cluster_id", "unverified"):
            with connect("writer", self.database) as conn:
                conn.execute("UPDATE clustering SET score_kind=%s WHERE iso3='AAA'", (kind,))
            with self.assertRaises(ValueError):
                self.writer.publish_scores(self.output, write=True)
            self.assertFalse(self.output.exists())
        self.assertEqual(self.scores(), [("DDD",9,None,None)])

    def test_existing_output_or_concurrent_publisher_prevents_publication(self):
        self.output.write_text("existing artifact")
        with self.assertRaises(FileExistsError):
            self.writer.publish_scores(self.output, write=True)
        self.assertEqual(self.scores(), [("DDD",9,None,None)])
        with connect("writer", self.database) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (PUBLICATION_LOCK,))
            with self.assertRaises(ValueError):
                self.writer.publish_scores(self.output.with_name("locked.json"), write=True)
        self.assertEqual(self.scores(), [("DDD",9,None,None)])

    def test_cli_preview_then_explicit_write(self):
        with patch("safetrip.config.load_environment"), patch.dict("os.environ", {
            "SAFETRIP_DB_BACKEND":"postgres", "SAFETRIP_DATABASE_URL":self.url}, clear=True):
            self.assertEqual(main(["publish-scores","--output",str(self.output)]), 0)
            self.assertEqual(self.scores(), [("DDD",9,None,None)])
            self.assertEqual(main(["publish-scores","--output",str(self.output.with_name("write.json")),"--write"]), 0)
            self.assertEqual(self.scores()[2], ("CCC",6,None,2))

    def test_history_preserves_exact_inputs_and_versions_after_later_updates(self):
        import hashlib
        from safetrip.persistence.history import encode
        payload = [{"iso3":"AAA","bert_score":1,"cleaned_text":"first input text"}]
        self.writer.publish("score", payload, publish_scores=True,
                            metadata={"model_version":"test-model-v1", "cleaning_version":None})
        first_run = self.writer.last_run_id
        with connect("writer", self.database) as conn:
            row = conn.execute("SELECT status,input_sha256,input_payload,metadata,published_rows FROM pipeline_runs WHERE run_id=%s", (first_run,)).fetchone()
            self.assertEqual(row[0], "succeeded")
            self.assertEqual(row[1], hashlib.sha256(encode(payload).encode()).hexdigest())
            self.assertEqual(row[2], payload)
            self.assertEqual(row[3]["model_version"], "test-model-v1")
            self.assertEqual(row[3]["scoring_version"], "legacy-v1")
            self.assertEqual(row[4], 4)
            first = conn.execute("SELECT safe_trip_score,inputs FROM score_history WHERE run_id=%s AND iso3='AAA'", (first_run,)).fetchone()
            self.assertEqual(first[0], 8.75)
            self.assertEqual(first[1]["bert_input"]["cleaned_text"], "first input text")
            self.assertEqual(first[1]["bert_run_metadata"]["model_version"], "test-model-v1")
            self.assertIsNone(first[1]["cluster_run_metadata"])
        self.writer.publish("score", [{"iso3":"AAA","bert_score":3,"cleaned_text":"second text"}],
                            publish_scores=True, metadata={"model_version":"test-model-v2"})
        with connect("writer", self.database) as conn:
            self.assertEqual(conn.execute("SELECT safe_trip_score,inputs FROM score_history WHERE run_id=%s AND iso3='AAA'", (first_run,)).fetchone(), first)
            current = conn.execute("SELECT last_run_id,published_at,safe_trip_score FROM scores WHERE iso3='AAA'").fetchone()
            self.assertEqual(current[0], self.writer.last_run_id)
            self.assertIsNotNone(current[1])
            self.assertEqual(current[2], 6.25)

    def test_preview_and_history_reads_do_not_create_runs(self):
        with connect("writer", self.database) as conn:
            before = conn.execute("SELECT count(*) FROM pipeline_runs").fetchone()[0]
        self.writer.publish_scores(self.output)
        self.writer.recent_runs()
        with connect("writer", self.database) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM pipeline_runs").fetchone()[0], before)

    def test_cli_failure_before_publication_is_recorded(self):
        source = self.output.with_name("malformed.json")
        source.write_text("not JSON")
        with connect("writer", self.database) as conn:
            before = conn.execute("SELECT count(*) FROM pipeline_runs").fetchone()[0]
        with patch("safetrip.config.load_environment"), patch.dict("os.environ", {
            "SAFETRIP_DB_BACKEND":"postgres", "SAFETRIP_DATABASE_URL":self.url}, clear=True):
            self.assertEqual(main(["score","--input",str(source),"--output",str(self.output),"--write"]), 1)
        with connect("writer", self.database) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM pipeline_runs").fetchone()[0], before + 1)
        run = self.writer.recent_runs()[0]
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["error_type"], "JSONDecodeError")
        self.assertIsNotNone(run["finished_at"])
        self.assertIsNone(run["input_sha256"])

    def test_history_is_private_and_score_snapshots_are_append_only(self):
        import psycopg
        statements = [("reader", "SELECT * FROM pipeline_runs"),
                      ("reader", "SELECT * FROM score_history"),
                      ("writer", "UPDATE score_history SET bert_score=0 WHERE false"),
                      ("writer", "DELETE FROM score_history WHERE false"),
                      ("writer", "DELETE FROM pipeline_runs WHERE false")]
        for role, statement in statements:
            with self.subTest(role=role, statement=statement), connect(role, self.database) as conn:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(statement)
                conn.rollback()

    def test_failure_record_does_not_store_exception_details(self):
        sentinel = "password=NEVER_STORE_THIS"
        with patch.object(self.writer, "_upsert", side_effect=RuntimeError(sentinel)), self.assertRaises(RuntimeError):
            self.writer.publish("score", [{"iso3":"AAA","bert_score":1}])
        from safetrip.persistence.history import encode
        run = self.writer.recent_runs()[0]
        self.assertEqual(run["error_type"], "RuntimeError")
        self.assertNotIn(sentinel, encode(run))
