"""Direct PostgreSQL batch writes with one transaction per publication.

Imports stay lazy so CLI help and lightweight tests need no database libraries.
"""
from datetime import datetime, timezone

TABLE_COLUMNS = {
    "countries": {"iso3", "iso2", "name", "continent", "flag_url"},
    "clustering": {"iso3", "clustering_score", "ppi", "gpi", "gti", "pvi"},
    "bert_scores": {"iso3", "cleaned_text", "bert_score"},
    "travel_advisories": {"iso3", "country_name", "country_code", "pub_date_raw",
                          "description_raw_html", "description_text", "last_fetched_at"},
}


class PostgresPublisher:
    def __init__(self, url):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        from sqlalchemy.pool import NullPool
        parsed = make_url(url)
        if parsed.drivername != "postgresql+psycopg" or parsed.username != "safetrip_writer":
            raise ValueError("A PostgreSQL writer account and psycopg URL are required.")
        # A one-shot batch job needs one connection, not a long-lived pool.
        self.engine = create_engine(parsed, poolclass=NullPool, hide_parameters=True,
                                    connect_args={"connect_timeout": 5, "options": "-c statement_timeout=30000"})

    @staticmethod
    def _upsert(conn, table, rows):
        from sqlalchemy import text
        allowed = TABLE_COLUMNS[table]
        for row in rows:
            if "iso3" not in row or not set(row) <= allowed:
                raise ValueError("Unexpected publication columns.")
            columns = sorted(row)
            assignments = ", ".join(f"{key}=EXCLUDED.{key}" for key in columns if key != "iso3")
            conflict = f"DO UPDATE SET {assignments}" if assignments else "DO NOTHING"
            statement = text(f"INSERT INTO public.{table} ({', '.join(columns)}) "
                             f"VALUES ({', '.join(':' + key for key in columns)}) "
                             f"ON CONFLICT (iso3) {conflict}")
            conn.execute(statement, row)

    def publish(self, command, artifact):
        from sqlalchemy import text
        if command not in {"ingest", "score", "refresh", "seed-countries", "import-clusters"}:
            raise ValueError("Unsupported publication command.")
        with self.engine.begin() as conn:
            if command in {"ingest", "refresh"}:
                rows = artifact["advisories"] if command == "refresh" else artifact
                now = datetime.now(timezone.utc)
                self._upsert(conn, "travel_advisories", [{**row, "last_fetched_at": now} for row in rows])
            if command in {"score", "refresh"}:
                rows = artifact["bert_scores"] if command == "refresh" else artifact
                countries = set(conn.execute(text("SELECT iso3 FROM public.countries")).scalars())
                if any(row["iso3"] not in countries for row in rows):
                    raise ValueError("Scored input contains an unknown country.")
                self._upsert(conn, "bert_scores", rows)
            if command in {"seed-countries", "import-clusters"}:
                self._upsert(conn, "countries" if command == "seed-countries" else "clustering", artifact)

    def close(self):
        self.engine.dispose()
