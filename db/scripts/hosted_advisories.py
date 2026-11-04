"""Explicit hosted writer setup/check/import; never modifies public scores.

Reads the existing admin connection from .env only for setup. Generated writer
credentials live in a mode-0600 ignored file, never argv, logs or SQL Editor.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import stat

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / '.local/supabase/advisory-writer.json'
CA = ROOT / '.local/supabase/prod-ca.crt'


def validate_target(config):
    import re
    if (not config.get('host','').endswith('.pooler.supabase.com')
        or str(config.get('port')) != '5432'
        or not re.fullmatch(r'safetrip_writer\.[a-z0-9]+',config.get('user',''))
        or not config.get('dbname') or not config.get('password') or not CA.is_file()):
        raise ValueError('Invalid hosted writer configuration or missing CA certificate')


def read_config():
    if CONFIG.is_symlink() or stat.S_IMODE(CONFIG.stat().st_mode) != 0o600:
        raise ValueError('Writer configuration must be a regular mode-0600 private file')
    value=json.loads(CONFIG.read_text())
    validate_target(value)
    return value


def connection(config):
    import psycopg
    validate_target(config)
    return psycopg.connect(**config, sslmode='verify-full',sslrootcert=str(CA),connect_timeout=15)


def check_writer(conn):
    """Read-only effective-identity and privilege checks, not speculative writes."""
    from psycopg import sql
    conn.read_only=True
    with conn.cursor() as c:
        c.execute("""SELECT current_user, r.rolsuper, r.rolcreaterole, r.rolcreatedb,
            r.rolbypassrls FROM pg_roles r WHERE r.rolname=current_user""")
        role=c.fetchone()
        if not conn.pgconn.ssl_in_use or role != ('safetrip_writer',False,False,False,False):
            raise ValueError('Unexpected effective database identity or insecure connection')
        c.execute("SELECT EXISTS(SELECT FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))")
        if c.fetchone()[0]:
            raise ValueError('Writer has unexpected role memberships')
        for schema in ['public','advisory']:
            c.execute('SELECT has_schema_privilege(current_user,%s,\'CREATE\')',(schema,))
            if c.fetchone()[0]: raise ValueError('Writer has schema creation access')
        for table in ['countries','culture','scores','clustering','bert_scores','travel_advisories']:
            for privilege in ['INSERT','UPDATE','DELETE','TRUNCATE']:
                c.execute('SELECT has_table_privilege(current_user,%s,%s)',('public.'+table,privilege))
                if c.fetchone()[0]: raise ValueError('Writer can modify legacy application tables')
            for privilege in ['INSERT','UPDATE']:
                c.execute('SELECT has_any_column_privilege(current_user,%s,%s)',('public.'+table,privilege))
                if c.fetchone()[0]: raise ValueError('Writer has legacy column write access')
        for table in ['documents','versions','coverage','observations','paragraphs','analyses','evidence']:
            c.execute(sql.SQL('SELECT 1 FROM advisory.{} LIMIT 0').format(sql.Identifier(table)))
            for privilege in ['SELECT','INSERT']:
                c.execute('SELECT has_table_privilege(current_user,%s,%s)',('advisory.'+table,privilege))
                if not c.fetchone()[0]: raise ValueError('Missing advisory access')
            for privilege in ['UPDATE','DELETE','TRUNCATE']:
                c.execute('SELECT has_table_privilege(current_user,%s,%s)',('advisory.'+table,privilege))
                if c.fetchone()[0]: raise ValueError('Advisory history is not append-only')
        for table, privileges in [('public.pipeline_runs',['SELECT','INSERT','UPDATE']),
                                  ('public.raw_feeds',['SELECT','INSERT'])]:
            for privilege in privileges:
                c.execute('SELECT has_table_privilege(current_user,%s,%s)',(table,privilege))
                if not c.fetchone()[0]: raise ValueError('Missing ingestion ledger access')
        c.execute('SELECT iso3 FROM public.countries LIMIT 1')


def enable_writer(conn, password):
    from psycopg import sql
    # libpq hashes locally. Plaintext password never appears in an SQL statement.
    verifier=conn.pgconn.encrypt_password(password.encode(),b'safetrip_writer',b'scram-sha-256').decode()
    conn.execute(sql.SQL('ALTER ROLE safetrip_writer LOGIN PASSWORD {}').format(sql.Literal(verifier)))


def setup():
    from dotenv import dotenv_values
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    import re
    admin=conninfo_to_dict(dotenv_values(ROOT/'.env').get('SUPABASE_DB_URL') or '')
    if (not admin.get('host','').endswith('.pooler.supabase.com')
        or admin.get('port') != '5432'
        or not re.fullmatch(r'postgres\.[a-z0-9]+',admin.get('user','')) or not CA.is_file()):
        raise ValueError('Expected existing Supabase admin session-pooler configuration and CA')
    writer={k:admin[k] for k in ['host','port','dbname']}
    writer['user']='safetrip_writer.'+admin['user'].split('.',1)[1]
    if CONFIG.exists():
        previous=read_config()
        if any(previous[k]!=v for k,v in writer.items()):
            raise ValueError('Existing writer file targets another project')
        writer=previous
    else:
        writer['password']=secrets.token_urlsafe(36)
    admin.update(sslmode='verify-full',sslrootcert=str(CA),connect_timeout=15)
    with psycopg.connect(**admin) as conn:
        if conn.execute('SELECT current_user').fetchone()[0]!='postgres':
            raise ValueError('Setup requires the audited owner connection')
        row=conn.execute("""SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls
            FROM pg_roles WHERE rolname='safetrip_writer'""").fetchone()
        if row != (False,False,False,False):
            raise ValueError('Unexpected writer role attributes')
        # Save before changing the role, so interruption cannot lose its password.
        if not CONFIG.exists():
            CONFIG.parent.mkdir(parents=True,exist_ok=True)
            descriptor=os.open(CONFIG,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as f:
                json.dump(writer,f);f.write('\n');f.flush();os.fsync(f.fileno())
        enable_writer(conn,writer['password'])
    with connection(writer) as conn:
        check_writer(conn)
    print('Writer login configured and checked. Generated credential saved privately under .local/supabase/.')
    print('Reader login and website configuration are unchanged. Do not share the credential file.')


def ingest(args):
    from safetrip.ingestion.multisource import normalize_bundle
    bundle=json.loads(Path(args.input).read_text())
    if set(bundle.get('iso3') or []) != {'CAN','JPN','USA'}:
        raise ValueError('Initial hosted import must be explicitly limited to CAN, JPN, USA')
    rows=normalize_bundle(bundle)
    if any(c['iso3'] not in {'CAN','JPN','USA'} for r in rows for c in r['coverage']):
        raise ValueError('Unexpected destination in initial capture')
    from sqlalchemy.engine import URL
    from safetrip.persistence.postgres import PostgresPublisher
    from safetrip.persistence.advisories import ingest_capture
    config=read_config()
    with connection(config) as conn: check_writer(conn)
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    # Reserve result before any database write; an empty file is not a success marker.
    with output.open('x') as f:
        url=URL.create('postgresql+psycopg',username=config['user'],password=config['password'],
            host=config['host'],port=int(config['port']),database=config['dbname'],
            query={'sslmode':'verify-full','sslrootcert':str(CA)})
        publisher=PostgresPublisher(url)
        try:
            report=ingest_capture(publisher,bundle)
            json.dump(report,f,indent=2);f.write('\n')
            print('Hosted advisory import committed. Run ID:',report['run_id'])
            print('Storage:',json.dumps(report['storage'],sort_keys=True))
            print('Existing scores were not published or changed by this command.')
        finally:
            publisher.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('setup');sub.add_parser('check')
    i=sub.add_parser('ingest');i.add_argument('--input',required=True);i.add_argument('--output',required=True)
    args=p.parse_args()
    try:
        if args.command=='setup': setup()
        elif args.command=='check':
            with connection(read_config()) as conn: check_writer(conn)
            print('Hosted writer identity, TLS and restricted permissions verified. No writes performed.')
        else: ingest(args)
        return 0
    except Exception as error:
        # Raw database exceptions may include SQL, credentials or connection details.
        print(f'Hosted advisory command failed ({type(error).__name__}); details suppressed. No successful import declared.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
