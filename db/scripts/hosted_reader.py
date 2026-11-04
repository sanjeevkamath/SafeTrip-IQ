"""Configure/check the read-only hosted account or start a private local preview.

Never writes .env, Vercel settings, or prints the reader credential.
"""
import argparse
import json
import os
import re
import secrets
import stat
import subprocess

from hosted_advisories import ROOT, CA

CONFIG = ROOT / '.local/supabase/advisory-reader.json'


def validate(config):
    if (not config.get('host','').endswith('.pooler.supabase.com')
        or str(config.get('port')) != '5432'
        or not re.fullmatch(r'safetrip_reader\.[a-z0-9]+',config.get('user',''))
        or not config.get('password') or not config.get('dbname') or not CA.is_file()):
        raise ValueError('Invalid hosted reader configuration or missing CA')


def read_config():
    if CONFIG.is_symlink() or stat.S_IMODE(CONFIG.stat().st_mode) != 0o600:
        raise ValueError('Reader file must be private mode 0600')
    config=json.loads(CONFIG.read_text());validate(config)
    return config


def connect(config):
    import psycopg
    validate(config)
    return psycopg.connect(**config,sslmode='verify-full',sslrootcert=str(CA),connect_timeout=15)


def check_reader(conn):
    conn.read_only=True
    role=conn.execute("""SELECT current_user,rolsuper,rolcreaterole,rolcreatedb,rolbypassrls
        FROM pg_roles WHERE rolname=current_user""").fetchone()
    if not conn.pgconn.ssl_in_use or role != ('safetrip_reader',False,False,False,False):
        raise ValueError('Unexpected reader identity or insecure connection')
    if conn.execute("SELECT EXISTS(SELECT FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))").fetchone()[0]:
        raise ValueError('Unexpected reader role memberships')
    return check_reader_grants(conn)


def check_reader_grants(conn):
    """Inspect catalog identities without resolving names inside a denied schema."""
    for schema, privilege in [('public','CREATE'),('advisory','CREATE'),('advisory','USAGE')]:
        if conn.execute('SELECT has_schema_privilege(current_user,%s,%s)',(schema,privilege)).fetchone()[0]:
            raise ValueError('Reader has unexpected schema access')
    tables=conn.execute("""SELECT c.oid, n.nspname||'.'||c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','advisory') AND c.relkind IN ('r','p','v','m')""").fetchall()
    approved={'public.countries','public.culture','public.scores','public.advisory_summaries'}
    for oid, table in tables:
        # Text relation names require schema USAGE during lookup. The reader
        # intentionally lacks that for advisory; use the catalog OID instead.
        can_read=conn.execute("SELECT has_table_privilege(current_user,%s::oid,'SELECT')",(oid,)).fetchone()[0]
        if can_read != (table in approved): raise ValueError('Unexpected reader table visibility')
        for privilege in ['INSERT','UPDATE','DELETE','TRUNCATE']:
            if conn.execute('SELECT has_table_privilege(current_user,%s::oid,%s)',(oid,privilege)).fetchone()[0]:
                raise ValueError('Reader can modify data')
        for privilege in ['INSERT','UPDATE']:
            if conn.execute('SELECT has_any_column_privilege(current_user,%s::oid,%s)',(oid,privilege)).fetchone()[0]:
                raise ValueError('Reader has column write access')
    # Exercise RLS and the owner's explicit display projection as the actual login.
    conn.execute('SELECT iso3 FROM public.countries LIMIT 1')
    conn.execute('SELECT iso3 FROM public.culture LIMIT 1')
    conn.execute('SELECT iso3 FROM public.scores LIMIT 1')
    return conn.execute('SELECT count(*) FROM public.advisory_summaries').fetchone()[0]


def enable_reader(conn,password):
    from psycopg import sql
    verifier=conn.pgconn.encrypt_password(password.encode(),b'safetrip_reader',b'scram-sha-256').decode()
    conn.execute(sql.SQL('ALTER ROLE safetrip_reader LOGIN PASSWORD {}').format(sql.Literal(verifier)))


def setup():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from dotenv import dotenv_values
    admin=conninfo_to_dict(dotenv_values(ROOT/'.env').get('SUPABASE_DB_URL') or '')
    if (not admin.get('host','').endswith('.pooler.supabase.com') or admin.get('port')!='5432'
        or not re.fullmatch(r'postgres\.[a-z0-9]+',admin.get('user','')) or not CA.is_file()):
        raise ValueError('Expected existing admin session pooler and CA')
    config={k:admin[k] for k in ['host','port','dbname']}
    config['user']='safetrip_reader.'+admin['user'].split('.',1)[1]
    if CONFIG.exists():
        previous=read_config()
        if any(previous[k]!=v for k,v in config.items()): raise ValueError('Reader file targets another project')
        config=previous
    else: config['password']=secrets.token_urlsafe(36)
    admin.update(sslmode='verify-full',sslrootcert=str(CA),connect_timeout=15)
    with psycopg.connect(**admin) as conn:
        if conn.execute('SELECT current_user').fetchone()[0]!='postgres': raise ValueError('Unexpected owner identity')
        attributes=conn.execute("SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname='safetrip_reader'").fetchone()
        if attributes != (False,False,False,False): raise ValueError('Unexpected reader role attributes')
        if not CONFIG.exists():
            CONFIG.parent.mkdir(parents=True,exist_ok=True)
            descriptor=os.open(CONFIG,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as f:
                json.dump(config,f);f.write('\n');f.flush();os.fsync(f.fileno())
        enable_reader(conn,config['password'])
    with connect(config) as conn: count=check_reader(conn)
    print(f'Reader login configured and checked. Display rows available: {count}.')
    print('Credential saved privately under .local/supabase/. Vercel and writer settings unchanged.')


def dev():
    from sqlalchemy.engine import URL
    config=read_config()
    with connect(config) as conn: check_reader(conn)
    env=os.environ.copy()
    env['SAFETRIP_ADVISORIES_ENABLED']='1'
    env['SAFETRIP_ADVISORY_DATABASE_URL']=URL.create('postgresql',username=config['user'],
        password=config['password'],host=config['host'],port=int(config['port']),database=config['dbname']).render_as_string(hide_password=False)
    env['SAFETRIP_ADVISORY_DATABASE_CA']=CA.read_text()
    print('Starting local website with hosted read-only advisories. No Vercel settings changed.',flush=True)
    return subprocess.call(['npm','run','dev'],cwd=ROOT/'frontend',env=env)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['setup','check','dev'])
    args=parser.parse_args()
    try:
        if args.command=='setup': setup()
        elif args.command=='check':
            with connect(read_config()) as conn: count=check_reader(conn)
            print(f'Reader identity, TLS, view reads and restricted permissions verified. Display rows: {count}.')
        else: return dev()
        return 0
    except KeyboardInterrupt: return 130
    except Exception as error:
        print(f'Hosted reader command failed ({type(error).__name__}); connection details suppressed.')
        return 1


if __name__=='__main__': raise SystemExit(main())
