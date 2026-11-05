"""Explicit hosted writer setup/check/import; never modifies public scores.

Reads the existing admin connection from .env only for setup. Generated writer
credentials live in a mode-0600 ignored file, never argv, logs or SQL Editor.
"""
import argparse
from datetime import datetime, timezone
import hashlib
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


class HostedValidationError(ValueError):
    """Controlled, credential-free rollout errors safe to show to the operator."""


def prepare_capture(args):
    from safetrip.ingestion.multisource import normalize_bundle, preview
    content=Path(args.input).read_bytes()
    bundle=json.loads(content)
    full=getattr(args,'all_destinations',False)
    if full:
        if bundle.get('iso3','missing') is not None:
            raise HostedValidationError('--all-destinations requires a complete --all capture, not a subset.')
    elif set(bundle.get('iso3') or []) != {'CAN','JPN','USA'}:
        raise HostedValidationError('Use the CAN/JPN/USA sample, or explicitly select --all-destinations.')
    rows=normalize_bundle(bundle)
    if not full and any(c['iso3'] not in {'CAN','JPN','USA'} for r in rows for c in r['coverage']):
        raise HostedValidationError('Unexpected destination in sample capture.')
    report=preview(rows,requested=bundle.get('iso3'))
    if not all(report['sources'].values()):
        raise HostedValidationError('Both official sources must contain documents for this rollout.')
    return bundle, rows, report, hashlib.sha256(content).hexdigest()


def catalogue_preflight(conn, rows):
    catalogue={r[0] for r in conn.execute('SELECT iso3 FROM public.countries').fetchall()}
    required={c['iso3'] for row in rows for c in row['coverage'] if c['iso3']}
    missing=sorted(required-catalogue)
    if missing:
        raise HostedValidationError('Country catalogue is missing capture keys: '+', '.join(missing))
    incoming={(r['source'],r['source_key']) for r in rows}
    previous=conn.execute('SELECT source,source_key FROM advisory.documents').fetchall()
    return {'catalogue_countries':len(catalogue),'mapped_capture_countries':len(required),
            'missing_country_keys':missing,
            'previous_documents_not_in_capture':[
                {'source':source,'source_key':key} for source,key in previous if (source,key) not in incoming]}


def review_records(rows, report):
    overlaps={(g['source'],key) for g in report['overlapping_country_documents'] for key in g['source_keys']}
    return [{'source':r['source'],'source_key':r['source_key'],'country_name':r['country_name'],
             'coverage':r['coverage'],'candidate_iso3':r['metadata'].get('covered_iso3_candidates',[]),
             'overlapping_documents':(r['source'],r['source_key']) in overlaps}
            for r in rows if any(c['scope']=='unresolved' for c in r['coverage'])
            or (r['source'],r['source_key']) in overlaps]


def preflight(args):
    _, rows, report, digest=prepare_capture(args)
    output=Path(args.output)
    if output.exists(): raise FileExistsError('Output exists')
    with connection(read_config()) as conn:
        check_writer(conn)
        catalogue=catalogue_preflight(conn,rows)
    plan={'format':'safetrip-hosted-import-plan-v1','created_at':datetime.now(timezone.utc).isoformat(),
          'mode':'all' if getattr(args,'all_destinations',False) else 'sample',
          'input_sha256':digest,'parser_version':report['parser_version'],
          'sources':report['sources'],'review_required':report['review_required'],
          'capture_bytes':Path(args.input).stat().st_size,
          'normalized_payload_bytes':sum(len(r['raw_payload']) for r in rows),
          'paragraphs':sum(len(section['paragraphs']) for r in rows for section in r['sections']),
          'review_records':review_records(rows,report),'database_preflight':catalogue,
          'public_scores_changed':False,'database_written':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f: json.dump(plan,f,indent=2);f.write('\n')
    print('Hosted preflight passed. No writes performed.')
    print('Documents by source:',json.dumps(plan['sources'],sort_keys=True))
    print('Review-required records retained separately:',plan['review_required'])
    print('Paragraphs to retain:',plan['paragraphs'])
    print('Previously stored documents absent from this capture:',len(catalogue['previous_documents_not_in_capture']))
    print('Plan saved to:',output)


def verify_plan(args, report, digest):
    if not getattr(args,'all_destinations',False): return
    if not getattr(args,'plan',None):
        raise HostedValidationError('A full import requires --plan from a successful preflight.')
    plan=json.loads(Path(args.plan).read_text())
    expected={'format':'safetrip-hosted-import-plan-v1','mode':'all','input_sha256':digest,
              'parser_version':report['parser_version'],'sources':report['sources'],
              'review_required':report['review_required'],'database_written':False}
    if any(plan.get(k)!=v for k,v in expected.items()) or plan.get('database_preflight',{}).get('missing_country_keys')!=[]:
        raise HostedValidationError('Plan does not match this validated capture/parser. Run preflight again.')


def ingest(args):
    bundle, rows, report, digest=prepare_capture(args)
    verify_plan(args,report,digest)
    from sqlalchemy.engine import URL
    from safetrip.persistence.postgres import PostgresPublisher
    from safetrip.persistence.advisories import ingest_capture
    config=read_config()
    with connection(config) as conn:
        check_writer(conn)
        catalogue_preflight(conn,rows)
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
    for command in ['preflight','ingest']:
        i=sub.add_parser(command);i.add_argument('--input',required=True);i.add_argument('--output',required=True)
        i.add_argument('--all-destinations',action='store_true',help='Explicitly select a complete worldwide capture.')
        if command=='ingest': i.add_argument('--plan',help='Required preflight JSON for a full import.')
    args=p.parse_args()
    try:
        if args.command=='setup': setup()
        elif args.command=='check':
            with connection(read_config()) as conn: check_writer(conn)
            print('Hosted writer identity, TLS and restricted permissions verified. No writes performed.')
        elif args.command=='preflight': preflight(args)
        else: ingest(args)
        return 0
    except Exception as error:
        # Raw database exceptions may include SQL, credentials or connection details.
        detail=str(error) if isinstance(error,HostedValidationError) else type(error).__name__
        print(f'Hosted advisory command failed ({detail}); connection details suppressed. No successful import declared.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
