import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from safetrip.cli import main
from safetrip.persistence.postgres import PostgresPublisher
from test_local_database import connect

ROOT = Path(__file__).resolve().parents[2]
URL = "postgresql+psycopg://safetrip_writer:writer_local_only@127.0.0.1:55432/safetrip"


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.writer = PostgresPublisher(URL)

    def tearDown(self):
        self.writer.close()

    def test_failed_refresh_rolls_back_earlier_advisory_write(self):
        with connect("reader") as conn:
            original = conn.execute("SELECT safe_trip_score FROM scores WHERE iso3='CAN'").fetchone()
        with self.assertRaises(ValueError):
            self.writer.publish("refresh", {
                "advisories": [{"iso3": "ZZZ", "description_text": "Must roll back"}],
                "bert_scores": [{"iso3": "ZZZ", "bert_score": 0}],
            })
        with connect("writer") as conn:
            self.assertIsNone(conn.execute("SELECT iso3 FROM travel_advisories WHERE iso3='ZZZ'").fetchone())
            self.assertEqual(conn.execute("SELECT safe_trip_score FROM scores WHERE iso3='CAN'").fetchone(), original)

    def test_real_cli_ingest_and_publication_crud(self):
        # Save and restore the two fixture rows after real committed publication.
        from psycopg.rows import dict_row
        from psycopg import sql
        tables = ("travel_advisories", "bert_scores", "clustering", "countries")
        with connect("writer", row_factory=dict_row) as conn:
            before = {table: conn.execute(sql.SQL("SELECT * FROM {} WHERE iso3 IN ('CAN','JPN')").format(sql.Identifier(table))).fetchall() for table in tables}
        try:
            with tempfile.TemporaryDirectory() as directory, patch("safetrip.config.load_environment"), patch.dict("os.environ", {
                "SAFETRIP_DB_BACKEND": "postgres", "SAFETRIP_DATABASE_URL": URL,
            }, clear=True), patch("safetrip.persistence.supabase.get_writer_client") as supabase:
                output = Path(directory) / "advisories.json"
                self.assertEqual(main(["ingest", "--input", str(ROOT / "tests/fixtures/advisories.xml"),
                    "--output", str(output), "--write"]), 0)
                supabase.assert_not_called()
                self.assertEqual(len(json.loads(output.read_text())), 2)
            self.writer.publish("score", [{"iso3": "CAN", "bert_score": 1, "cleaned_text": "test classification"}])
            self.writer.publish("import-clusters", [{"iso3": "CAN", "clustering_score": 1}])
            self.writer.publish("seed-countries", [{"iso3": "CAN", "name": "Canada", "iso2": "CA"}])
            with connect("writer") as conn:
                self.assertEqual(conn.execute("SELECT bert_score FROM bert_scores WHERE iso3='CAN'").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT clustering_score FROM clustering WHERE iso3='CAN'").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT continent FROM countries WHERE iso3='CAN'").fetchone()[0], "North America")
                self.assertEqual(conn.execute("SELECT safe_trip_score FROM scores WHERE iso3='CAN'").fetchone()[0], 10)
        finally:
            with self.writer.engine.begin() as conn:
                for table in reversed(tables):
                    self.writer._upsert(conn, table, before[table])

    def test_invalid_columns_roll_back_batch(self):
        with self.assertRaises(ValueError):
            self.writer.publish("ingest", [{"iso3": "ZZZ", "description_text": "valid first row"},
                                            {"iso3": "ZZZ", "unexpected_column": "bad second row"}])
        with connect("writer") as conn:
            self.assertIsNone(conn.execute("SELECT iso3 FROM travel_advisories WHERE iso3='ZZZ'").fetchone())

    def test_writer_role_required(self):
        with self.assertRaises(ValueError):
            PostgresPublisher(URL.replace("safetrip_writer:", "safetrip_migrator:"))
