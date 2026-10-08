"""Read-only, consistent export of the six application tables to ignored files.

Requires python-dotenv and psycopg. No population modules are imported.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("countries", "culture", "scores", "bert_scores", "clustering", "travel_advisories")


def main():
    from dotenv import dotenv_values
    import psycopg
    from psycopg import sql, IsolationLevel
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.rows import dict_row

    configuration = dotenv_values(ROOT / ".env")
    connection = conninfo_to_dict(configuration.get("SUPABASE_DB_URL") or "")
    if not connection.get("host", "").endswith(".pooler.supabase.com"):
        raise ValueError("Expected the configured Supabase pooler.")
    connection.update(sslmode="verify-full",
                      sslrootcert=str(ROOT / ".local/supabase/prod-ca.crt"),
                      connect_timeout=15)
    os.umask(0o077)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / ".local/baselines" / stamp
    output.mkdir(parents=True, mode=0o700)
    manifest = {"captured_at_utc": stamp, "read_only": True,
                "isolation": "repeatable read", "tables": {}}
    with psycopg.connect(**connection, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_setting('transaction_read_only') AS read_only")
            if cursor.fetchone()["read_only"] != "on" or not conn.pgconn.ssl_in_use:
                raise RuntimeError("Read-only/TLS verification failed.")
            for table in TABLES:
                cursor.execute(sql.SQL("SELECT * FROM public.{} ORDER BY iso3").format(sql.Identifier(table)))
                rows = cursor.fetchall()
                contents = json.dumps(rows, indent=2, ensure_ascii=False, default=str).encode()
                (output / f"{table}.json").write_bytes(contents)
                manifest["tables"][table] = {"rows": len(rows),
                    "sha256": hashlib.sha256(contents).hexdigest()}
    # A completed manifest marks a successful snapshot; partial exports have none.
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Read-only snapshot:", output)
    for table, details in manifest["tables"].items():
        print(table, "rows:", details["rows"])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Snapshot failed:", type(error).__name__, "(connection details suppressed)")
        raise SystemExit(1)
