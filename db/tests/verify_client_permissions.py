"""Integration check for an isolated restore, NEVER a production connection.

Requires a restored public-schema.sql in the dedicated local database below.
Uses synthetic rows and rolls back each permission probe. Does not load .env.
"""

from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.errors import InsufficientPrivilege


ROOT = Path(__file__).resolve().parents[2]
TABLES = ("countries", "culture", "scores", "bert_scores", "clustering", "travel_advisories")
PUBLIC_READS = {"countries", "culture", "scores"}
CONNECTION = dict(host="/tmp/safetrip-phase0-postgres-socket", port=55437,
                  dbname="safetrip_permission_test", user="postgres")


def check(condition, description):
    if not condition:
        raise AssertionError(description)


def probe(conn, role, statement, denied=False):
    try:
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        result = conn.execute(statement)
        rows = result.fetchall() if result.description else None
        if denied:
            raise AssertionError(f"Unexpected permission granted to {role}")
        return rows
    except InsufficientPrivilege:
        if not denied:
            raise
    finally:
        conn.rollback()


def run():
    with psycopg.connect(**CONNECTION, autocommit=True) as conn:
        # Stop immediately if the target is not the dedicated local fixture DB.
        row = conn.execute("SELECT current_database(), inet_server_addr()").fetchone()
        check(row == ("safetrip_permission_test", None), "Not the local test database")
        migration = (ROOT / "db/security/002_client_read_only.sql").read_text()
        conn.execute(migration)
        conn.execute(migration)  # The migration must be safe to rerun.
        conn.execute("INSERT INTO public.countries (iso3,name) VALUES ('ZZZ','Synthetic test country')")
        for table in TABLES[1:]:
            conn.execute(sql.SQL("INSERT INTO public.{} (iso3) VALUES ('ZZZ')").format(sql.Identifier(table)))

        conn.autocommit = False
        denies = 0
        reads = 0
        for role in ("anon", "authenticated"):
            for table in TABLES:
                allowed = table in PUBLIC_READS if role == "anon" else table == "countries"
                rows = probe(conn, role, sql.SQL("SELECT iso3 FROM public.{}").format(sql.Identifier(table)),
                             denied=not allowed)
                if allowed:
                    check(rows == [("ZZZ",)], "Expected public fixture missing")
                    reads += 1
                else:
                    denies += 1
                identifier = sql.Identifier(table)
                for statement in (
                    sql.SQL("INSERT INTO public.{} (iso3) VALUES ('QQQ')").format(identifier),
                    sql.SQL("UPDATE public.{} SET iso3='QQQ' WHERE iso3='ZZZ'").format(identifier),
                    sql.SQL("DELETE FROM public.{} WHERE iso3='ZZZ'").format(identifier),
                    sql.SQL("TRUNCATE public.{} CASCADE").format(identifier),
                ):
                    probe(conn, role, statement, denied=True)
                    denies += 1

        # Exercise the actual BYPASSRLS role with the backed-up table grants.
        fields = {"countries": ("name", "Changed synthetic country"),
                  "culture": ("language", "Synthetic language"),
                  "scores": ("bert_score", 2), "bert_scores": ("bert_score", 2),
                  "clustering": ("clustering_score", 2),
                  "travel_advisories": ("country_name", "Changed synthetic country")}
        try:
            conn.execute("SET LOCAL ROLE service_role")
            conn.execute("INSERT INTO public.countries (iso3,name) VALUES ('QQQ','Synthetic writer country')")
            for table in TABLES[1:]:
                conn.execute(sql.SQL("INSERT INTO public.{} (iso3) VALUES ('QQQ')").format(sql.Identifier(table)))
            for table, (field, value) in fields.items():
                result = conn.execute(sql.SQL("UPDATE public.{} SET {}=%s WHERE iso3='QQQ'").format(
                    sql.Identifier(table), sql.Identifier(field)), (value,))
                check(result.rowcount == 1, "Trusted update affected wrong number of rows")
                result = conn.execute(sql.SQL("SELECT {} FROM public.{} WHERE iso3='QQQ'").format(
                    sql.Identifier(field), sql.Identifier(table))).fetchone()
                check(result == (value,), "Trusted update not reflected by read")
            for table in reversed(TABLES):
                result = conn.execute(sql.SQL("DELETE FROM public.{} WHERE iso3='QQQ'").format(sql.Identifier(table)))
                check(result.rowcount == 1, "Trusted delete affected wrong number of rows")
        finally:
            conn.rollback()

        # Verify creator-specific defaults on future objects, without persisting them.
        try:
            conn.execute("CREATE TABLE public.phase0_future_table (id integer)")
            conn.execute("CREATE SEQUENCE public.phase0_future_sequence")
            for role in ("anon", "authenticated"):
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN"):
                    value = conn.execute("SELECT has_table_privilege(%s,'public.phase0_future_table',%s)",
                                         (role, privilege)).fetchone()[0]
                    check(not value, "Future table unexpectedly grants client access")
                for privilege in ("SELECT", "UPDATE", "USAGE"):
                    value = conn.execute("SELECT has_sequence_privilege(%s,'public.phase0_future_sequence',%s)",
                                         (role, privilege)).fetchone()[0]
                    check(not value, "Future sequence unexpectedly grants client access")
            for table in TABLES:
                for role in ("anon", "authenticated"):
                    for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN"):
                        value = conn.execute("SELECT has_table_privilege(%s,%s,%s)",
                                             (role, 'public.' + table, privilege)).fetchone()[0]
                        check(not value, "Unexpected remaining client table privilege")
        finally:
            conn.rollback()
        print(f"PASS: {reads} intended reads; {denies} denied client operations.")
        print("PASS: service_role INSERT/UPDATE/SELECT/DELETE on all six tables.")
        print("PASS: remaining client table privileges and future table/sequence defaults.")
        print("PASS: migration applied twice. All probes used only synthetic local records.")


if __name__ == "__main__":
    run()
