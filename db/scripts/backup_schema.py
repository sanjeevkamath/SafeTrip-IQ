"""Export schema/ACLs without rows; credentials and exports stay out of Git.

Requires pg_dump plus python-dotenv and psycopg. Use --pg-dump for an isolated
PostgreSQL client installation. Never imports a population script.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def main():
    from dotenv import dotenv_values
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.rows import dict_row

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-dump", default="pg_dump")
    args = parser.parse_args()
    config = dotenv_values(ROOT / ".env")
    connection = conninfo_to_dict(config.get("SUPABASE_DB_URL") or "")
    required = ("host", "user", "password", "dbname")
    if not all(connection.get(name) for name in required):
        raise ValueError("SUPABASE_DB_URL is incomplete.")
    if not connection["host"].endswith(".pooler.supabase.com"):
        raise ValueError("Expected the configured Supabase session pooler.")
    if connection.get("port") != "5432":
        raise ValueError("Use the session pooler on port 5432 for this backup.")
    base = ROOT / ".local" / "supabase"
    certificate = base / "prod-ca.crt"
    if not certificate.is_file():
        raise ValueError("Download the project's CA certificate first.")
    os.umask(0o077)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = base / ("schema-backup-" + stamp)
    destination.mkdir(parents=True, mode=0o700)

    # Collect permission metadata in one read-only transaction. These queries
    # read PostgreSQL catalogs, never application records or role passwords.
    queries = {
        "roles": """SELECT rolname, rolsuper, rolinherit, rolcreaterole,
                   rolcreatedb, rolcanlogin, rolbypassrls FROM pg_roles
                   WHERE rolname IN ('anon','authenticated','service_role')""",
        "memberships": """SELECT parent.rolname AS granted_role,
                          child.rolname AS member_role, m.admin_option
                          FROM pg_auth_members m
                          JOIN pg_roles parent ON parent.oid=m.roleid
                          JOIN pg_roles child ON child.oid=m.member
                          ORDER BY child.rolname, parent.rolname""",
        "policies": "SELECT * FROM pg_policies WHERE schemaname='public'",
        "tables": """SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                      pg_get_userbyid(c.relowner) AS owner, c.relacl::text AS acl
                      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                      WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m')""",
        "column_acls": """SELECT c.relname, a.attname, a.attacl::text AS acl
                           FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
                           JOIN pg_namespace n ON n.oid=c.relnamespace
                           WHERE n.nspname='public' AND a.attacl IS NOT NULL
                           AND a.attnum>0 AND NOT a.attisdropped""",
        "default_acls": """SELECT pg_get_userbyid(d.defaclrole) AS owner,
                            n.nspname AS schema_name, d.defaclobjtype,
                            d.defaclacl::text AS acl FROM pg_default_acl d
                            LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace""",
        "effective_privileges": """SELECT c.relname AS table_name, r.role_name,
            has_table_privilege(r.role_name,c.oid,'SELECT') AS can_select,
            has_table_privilege(r.role_name,c.oid,'INSERT') AS can_insert,
            has_table_privilege(r.role_name,c.oid,'UPDATE') AS can_update,
            has_table_privilege(r.role_name,c.oid,'DELETE') AS can_delete,
            has_table_privilege(r.role_name,c.oid,'TRUNCATE') AS can_truncate,
            has_any_column_privilege(r.role_name,c.oid,'INSERT') AS column_insert,
            has_any_column_privilege(r.role_name,c.oid,'UPDATE') AS column_update
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN (VALUES ('anon'),('authenticated'),('service_role')) r(role_name)
            WHERE n.nspname='public' AND c.relkind IN ('r','p')
            ORDER BY c.relname,r.role_name""",
    }
    verified_connection = {**connection, "sslmode": "verify-full",
                           "sslrootcert": str(certificate), "connect_timeout": 15}
    with psycopg.connect(**verified_connection, row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_setting('server_version') AS version, "
                           "current_setting('transaction_read_only') AS read_only")
            server = cursor.fetchone()
            if server["read_only"] != "on" or not conn.pgconn.ssl_in_use:
                raise RuntimeError("Read-only/TLS verification failed.")
            audit = {}
            for name, query in queries.items():
                cursor.execute(query)
                audit[name] = cursor.fetchall()
    (destination / "permissions.json").write_text(json.dumps(audit, indent=2, default=str))

    # Keep the password out of argv and shell command text. Explicit connection
    # parameters prevent accidental fallback to a local database or weaker TLS.
    env = os.environ.copy()
    for name in list(env):
        if name.startswith("PG"):
            del env[name]
    for field, setting in {"host":"PGHOST", "port":"PGPORT", "user":"PGUSER",
                           "password":"PGPASSWORD", "dbname":"PGDATABASE"}.items():
        env[setting] = connection[field]
    env.update(PGSSLMODE="verify-full", PGSSLROOTCERT=str(certificate), PGCONNECT_TIMEOUT="15")
    output = destination / "schema.sql"
    result = subprocess.run(
        [args.pg_dump, "--schema-only", "--no-password", "--lock-wait-timeout=10s",
         "--file", str(output)], env=env, capture_output=True, timeout=180,
    )
    if result.returncode:
        raise RuntimeError("pg_dump failed; no successful backup declared. Output suppressed.")
    contents = output.read_bytes()
    if not contents or b"PostgreSQL database dump complete" not in contents:
        raise RuntimeError("Backup completion marker missing.")
    # Separate application-only dump supports a local restore without requiring
    # Supabase's auth/storage/extension infrastructure.
    application_output = destination / "public-schema.sql"
    application_result = subprocess.run(
        [args.pg_dump, "--schema-only", "--schema=public", "--no-password",
         "--lock-wait-timeout=10s", "--file", str(application_output)],
        env=env, capture_output=True, timeout=180,
    )
    if application_result.returncode:
        raise RuntimeError("Application schema export failed; details suppressed.")
    application_contents = application_output.read_bytes()
    if b"PostgreSQL database dump complete" not in application_contents:
        raise RuntimeError("Application schema completion marker missing.")
    manifest = {
        "created_at_utc": stamp, "server_version": server["version"],
        "schema_only": True, "includes_owners_and_acls": True,
        "includes_role_passwords": False, "restore_tested": False,
        "sha256": hashlib.sha256(contents).hexdigest(), "bytes": len(contents),
        "public_schema_sha256": hashlib.sha256(application_contents).hexdigest(),
        "scope": "Database schema plus separate role/permission metadata; no application rows.",
        "limitations": "Role/extension dependencies on Supabase remain; not a portable full-platform restore.",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Schema backup completed:", destination)
    print("Schema bytes:", len(contents))
    print("Public relations inventoried:", len(audit["tables"]))
    print("Owner/ACL statements retained; no application rows exported.")
    print("Restore test remains pending.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not let a connection exception reveal configuration values.
        print("Schema backup failed:", type(error).__name__, "(details suppressed)")
        raise SystemExit(1)
