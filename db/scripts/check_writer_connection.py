"""Read-only check of the maintenance client; never runs population scripts.

Run from the repository root:
    python -m db.scripts.check_writer_connection
"""

import sys

if __package__:
    from .supabase_writer import get_writer_client
else:
    from supabase_writer import get_writer_client


def main():
    try:
        client = get_writer_client()
        for table in ("countries", "bert_scores"):
            # A normal SELECT, bounded to one identifier. No record contents
            # are logged. Reading bert_scores also exercises an internal table.
            result = client.table(table).select("iso3").limit(1).execute()
            print(f"SELECT {table}: succeeded; rows returned={len(result.data)} (limit 1)")
    except Exception as error:
        # SDK/network errors can contain request details. Keep credentials and
        # raw exception text out of console output and shared audit records.
        print(f"Read-only connection check failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    print("Read-only checks passed. No inserts, updates, deletes, or RPC calls were made.")
    print("This does not verify write permission or the deployed website configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
