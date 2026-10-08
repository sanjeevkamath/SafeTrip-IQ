"""Local-only integration checks. No production configuration is consumed."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("countries", "culture", "scores", "bert_scores", "clustering", "travel_advisories")


def connect(role, database="safetrip", **kwargs):
    passwords = {"admin": "safetrip_local_only", "reader": "reader_local_only",
                 "writer": "writer_local_only", "migrator": "migrator_local_only"}
    return psycopg.connect(host="127.0.0.1", port=55432, dbname=database,
                           user=f"safetrip_{role}", password=passwords[role], **kwargs)


class LocalDatabaseTests(unittest.TestCase):
    def test_reader_baseline_and_optional_data(self):
        expected = {row["iso3"]: row for row in json.loads(
            (ROOT / "tests/fixtures/legacy_scores.json").read_text())["rows"]}
        with connect("reader") as conn:
            rows = conn.execute("SELECT iso3, safe_trip_score, bert_score, clustering_score FROM scores ORDER BY iso3").fetchall()
            self.assertEqual([r[0] for r in rows], ["CAN", "JPN", "USA"])
            for iso3, score, bert, cluster in rows:
                self.assertEqual((score, bert, cluster), (expected[iso3]["safe_trip_score"],
                    expected[iso3]["bert_score"], expected[iso3]["clustering_score"]))
            self.assertEqual(conn.execute("SELECT count(*) FROM countries").fetchone()[0], 3)
            self.assertEqual(conn.execute("SELECT count(*) FROM culture WHERE iso3='USA'").fetchone()[0], 0)

    def test_reader_cannot_write_or_read_internal_tables(self):
        statements = []
        for table in TABLES:
            statements.extend([f"INSERT INTO {table} (iso3) VALUES ('ZZZ')",
                               f"UPDATE {table} SET iso3=iso3 WHERE false",
                               f"DELETE FROM {table} WHERE false", f"TRUNCATE {table}"])
        statements.extend(f"SELECT * FROM {table}" for table in TABLES if table not in ("countries", "culture", "scores"))
        statements.extend(["CREATE TABLE public.forbidden (id int)", "SET ROLE safetrip_writer"])
        for statement in statements:
            with self.subTest(statement=statement), connect("reader") as conn:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(statement)
                conn.rollback()

    def test_writer_can_write_all_tables_without_owning_them(self):
        with connect("writer") as conn:
            try:
                conn.execute("INSERT INTO countries (iso3, name) VALUES ('ZZZ', 'Integration fixture')")
                for table in TABLES[1:]:
                    conn.execute(sql.SQL("INSERT INTO {} (iso3) VALUES ('ZZZ')").format(sql.Identifier(table)))
                for table in TABLES:
                    result = conn.execute(sql.SQL("UPDATE {} SET iso3=iso3 WHERE iso3='ZZZ' RETURNING iso3").format(sql.Identifier(table))).fetchone()
                    self.assertEqual(result[0], "ZZZ")
                for table in reversed(TABLES):
                    conn.execute(sql.SQL("DELETE FROM {} WHERE iso3='ZZZ'").format(sql.Identifier(table)))
            finally:
                conn.rollback()
        for statement in ("TRUNCATE scores", "CREATE TABLE public.forbidden (id int)",
                          "ALTER TABLE scores DISABLE ROW LEVEL SECURITY", "SET ROLE safetrip_migrator"):
            with self.subTest(statement=statement), connect("writer") as conn:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(statement)
                conn.rollback()

    def test_roles_rls_and_foreign_keys(self):
        with connect("admin") as conn:
            roles = conn.execute("SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname IN ('safetrip_reader','safetrip_writer','safetrip_migrator')").fetchall()
            self.assertEqual(len(roles), 3)
            for role in roles:
                self.assertEqual(role[1:], (False, False, False, False))
            for table in TABLES:
                self.assertEqual(conn.execute("SELECT relrowsecurity, pg_get_userbyid(relowner) FROM pg_class WHERE oid=%s::regclass", (f"public.{table}",)).fetchone(), (True, "safetrip_migrator"))
        with connect("writer") as conn:
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                conn.execute("INSERT INTO bert_scores (iso3) VALUES ('ZZZ')")
            conn.rollback()

    def test_seed_is_repeatable(self):
        def snapshot(conn):
            return {table: conn.execute(sql.SQL("SELECT * FROM {} ORDER BY iso3").format(sql.Identifier(table))).fetchall() for table in TABLES}
        with connect("writer") as conn:
            before = snapshot(conn)
            seed = "\n".join(line for line in (ROOT / "db/local/seed.sql").read_text().splitlines()
                             if not line.startswith("\\") and line not in ("BEGIN;", "COMMIT;"))
            try:
                conn.execute(seed)
                conn.execute(seed)
                self.assertEqual(snapshot(conn), before)
            finally:
                conn.rollback()

    def test_migration_upgrade_downgrade_on_disposable_database(self):
        database = "safetrip_test_" + uuid.uuid4().hex[:12]
        with connect("admin", autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER safetrip_migrator").format(sql.Identifier(database)))
            try:
                env = dict(os.environ, SAFETRIP_MIGRATION_URL=f"postgresql+psycopg://safetrip_migrator:migrator_local_only@127.0.0.1:55432/{database}")
                for operation, revision in (("upgrade", "head"), ("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
                    subprocess.run([sys.executable, "-m", "alembic", operation, revision], cwd=ROOT, env=env, check=True, capture_output=True)
                    with connect("migrator", database) as conn:
                        count = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename != 'alembic_version'").fetchone()[0]
                        self.assertEqual(count, 0 if operation == "downgrade" else 6)
            finally:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


if __name__ == "__main__":
    unittest.main()
