"""Import the reviewed snapshot into fixed local safetrip_full; never load .env."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
URL = 'postgresql+psycopg://safetrip_writer:writer_local_only@127.0.0.1:55432/safetrip_full'


def main():
    from safetrip.persistence.baseline import load_baseline
    from safetrip.jobs import save_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if Path(args.output).exists():
        raise ValueError('Choose an unused output file.')
    tables, metadata, report = load_baseline(args.snapshot, ROOT / 'data/baseline/clustering/clusters.csv')
    report['written'] = False
    if args.write:
        import psycopg
        from safetrip.persistence.postgres import PostgresPublisher
        with psycopg.connect('host=127.0.0.1 port=55432 dbname=safetrip user=safetrip_admin password=safetrip_local_only', autocommit=True) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname='safetrip_full'").fetchone():
                conn.execute('CREATE DATABASE safetrip_full OWNER safetrip_migrator')
            conn.execute('REVOKE ALL ON DATABASE safetrip_full FROM PUBLIC')
            conn.execute('GRANT CONNECT ON DATABASE safetrip_full TO safetrip_reader,safetrip_writer,safetrip_migrator')
        with psycopg.connect('host=127.0.0.1 port=55432 dbname=safetrip_full user=safetrip_migrator password=migrator_local_only') as conn:
            conn.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            conn.execute('GRANT USAGE ON SCHEMA public TO safetrip_reader,safetrip_writer')
        migration_url = URL.replace('safetrip_writer:writer_local_only', 'safetrip_migrator:migrator_local_only')
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT,
                       env=dict(os.environ, SAFETRIP_MIGRATION_URL=migration_url), check=True, capture_output=True)
        publisher = PostgresPublisher(URL)
        try:
            coverage = publisher.import_baseline(tables, metadata)
            if coverage != report['coverage']:
                raise RuntimeError('Unexpected imported coverage.')
            report.update(written=True, database='safetrip_full', run_id=str(publisher.last_run_id))
        finally:
            publisher.close()
    save_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Local baseline import failed ({type(error).__name__}); check input integrity and whether safetrip_full is empty.', file=sys.stderr)
        raise SystemExit(1)
