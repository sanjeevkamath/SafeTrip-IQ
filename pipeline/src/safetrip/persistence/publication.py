"""Explicit backend selection. A failed backend never falls back to another DB."""
import os


class SupabasePublisher:
    def __init__(self):
        from safetrip.persistence.supabase import get_writer_client
        self.client = get_writer_client()

    def publish(self, command, artifact):
        from safetrip.persistence import repository
        if command in {"ingest", "refresh"}:
            repository.write_advisories(self.client, artifact["advisories"] if command == "refresh" else artifact)
        if command in {"score", "refresh"}:
            repository.write_bert_scores(self.client, artifact["bert_scores"] if command == "refresh" else artifact)
        if command in {"seed-countries", "import-clusters"}:
            repository.write_rows(self.client, "countries" if command == "seed-countries" else "clustering", artifact)

    def close(self):
        pass


def get_publisher():
    backend = os.environ.get("SAFETRIP_DB_BACKEND", "supabase")
    if backend == "supabase":
        return SupabasePublisher()
    if backend == "postgres":
        from safetrip.persistence.postgres import PostgresPublisher
        return PostgresPublisher(os.environ.get("SAFETRIP_DATABASE_URL", ""))
    raise ValueError("Unsupported database backend.")
