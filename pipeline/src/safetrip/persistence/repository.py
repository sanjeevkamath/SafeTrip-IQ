"""Interim Supabase persistence. Direct PostgreSQL and transactions come next."""
from datetime import datetime, timezone


def read_advisories(client):
    return client.table("travel_advisories").select("iso3, description_text").execute().data


def write_advisories(client, records):
    now = datetime.now(timezone.utc).isoformat()
    rows = [{**row, "last_fetched_at": now} for row in records]
    if rows:
        client.table("travel_advisories").upsert(rows, on_conflict="iso3").execute()


def write_bert_scores(client, rows):
    # Validate every country before the first batch is written.
    valid = {row["iso3"] for row in client.table("countries").select("iso3").execute().data}
    if any(row["iso3"] not in valid for row in rows):
        raise ValueError("Scored input contains a country absent from the database.")
    for start in range(0, len(rows), 16):
        client.table("bert_scores").upsert(rows[start:start + 16], on_conflict="iso3").execute()


def write_rows(client, table, rows):
    if table not in {"countries", "clustering"}:
        raise ValueError("Unsupported maintenance table.")
    if rows:
        client.table(table).upsert(rows, on_conflict="iso3").execute()
