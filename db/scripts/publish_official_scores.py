"""Configure/check the scoped score publisher or explicitly publish a reviewed preview."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import stat
from hosted_advisories import ROOT,CA

ROLE='safetrip_score_publisher'
CONFIG=ROOT/'.local/supabase/official-score-publisher.json'


def config_file():
    if CONFIG.is_symlink() or stat.S_IMODE(CONFIG.stat().st_mode)!=0o600:raise ValueError('Publisher file must be private mode 0600')
    value=json.loads(CONFIG.read_text())
    if (not value.get('host','').endswith('.pooler.supabase.com') or str(value.get('port'))!='5432'
        or not re.fullmatch(ROLE+r'\.[a-z0-9]+',value.get('user','')) or not value.get('password') or not CA.is_file()):
        raise ValueError('Invalid publisher target')
    return value


def connect(config):
    import psycopg
    return psycopg.connect(**config,sslmode='verify-full',sslrootcert=str(CA),connect_timeout=15)


def check(c):
    c.read_only=True
    attrs=c.execute('SELECT current_user,rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
    if not c.pgconn.ssl_in_use or attrs!=(ROLE,False,False,False,False):raise ValueError('Unexpected publisher identity/TLS')
    if c.execute('SELECT EXISTS(SELECT FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))').fetchone()[0]:
        raise ValueError('Unexpected publisher membership')
    if c.execute("SELECT has_schema_privilege(current_user,'advisory','USAGE') OR has_schema_privilege(current_user,'public','CREATE')").fetchone()[0]:
        raise ValueError('Unexpected publisher schema privileges')
    for column in ['bert_score','clustering_score']:
        for privilege in ['INSERT','UPDATE']:
            if c.execute("SELECT has_column_privilege(current_user,'public.scores',%s,%s)",(column,privilege)).fetchone()[0]:
                raise ValueError('Publisher may alter historical model inputs')
    for table in ['public.countries','public.clustering','public.bert_scores','public.travel_advisories']:
        for privilege in ['INSERT','UPDATE','DELETE','TRUNCATE']:
            if c.execute('SELECT has_table_privilege(current_user,%s,%s)',(table,privilege)).fetchone()[0]:
                raise ValueError('Unexpected source-table mutation privileges')
    for column in ['safe_trip_score','official_us_level','official_us_component','clustering_component',
                   'scoring_version','score_run_id','score_published_at']:
        if not c.execute("SELECT has_column_privilege(current_user,'public.scores',%s,'UPDATE')",(column,)).fetchone()[0]:
            raise ValueError('Missing scoped publication grant')
    if c.execute("SELECT has_table_privilege(current_user,'public.scores','DELETE') OR has_table_privilege(current_user,'public.scores','TRUNCATE')").fetchone()[0]:
        raise ValueError('Publisher may erase score rows')
    c.execute('SELECT 1 FROM public.advisory_summaries LIMIT 0')
    c.execute('SELECT 1 FROM public.official_score_history LIMIT 0')


def enable_publisher(c,password):
    from psycopg import sql
    verifier=c.pgconn.encrypt_password(password.encode(),ROLE.encode(),b'scram-sha-256').decode()
    c.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(ROLE),sql.Literal(verifier)))


def setup():
    from dotenv import dotenv_values
    from psycopg.conninfo import conninfo_to_dict
    admin=conninfo_to_dict(dotenv_values(ROOT/'.env').get('SUPABASE_DB_URL') or '')
    if (not admin.get('host','').endswith('.pooler.supabase.com') or admin.get('port')!='5432'
        or not re.fullmatch(r'postgres\.[a-z0-9]+',admin.get('user','')) or not CA.is_file()):
        raise ValueError('Expected existing Supabase admin session pooler and CA')
    value={k:admin[k] for k in ['host','port','dbname']};value['user']=ROLE+'.'+admin['user'].split('.',1)[1]
    if CONFIG.exists():
        old=config_file()
        if any(old[k]!=v for k,v in value.items()):raise ValueError('Publisher file targets another project')
        value=old
    else:value['password']=secrets.token_urlsafe(36)
    with connect(admin) as c:
        if c.execute('SELECT current_user').fetchone()[0]!='postgres':raise ValueError('Unexpected setup owner')
        attrs=c.execute('SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname=%s',(ROLE,)).fetchone()
        if attrs!=(False,False,False,False):raise ValueError('Missing or unexpected publisher role; apply migration first')
        if not CONFIG.exists():
            CONFIG.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(CONFIG,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:json.dump(value,f);f.write('\n');f.flush();os.fsync(f.fileno())
        enable_publisher(c,value['password'])
    with connect(value) as c:check(c)
    print('Scoped publisher configured and checked; private credential saved under .local/supabase/. No scores published.')


def publish(args):
    from sqlalchemy.engine import URL
    from safetrip.persistence.official_scores import OfficialScorePublisher
    from safetrip.persistence.postgres import ScorePublicationError
    from urllib.parse import urlsplit
    import requests
    site=urlsplit(args.site)
    if (site.scheme!='https' or not site.hostname or site.username or site.password or site.query or site.fragment
        or site.path not in ('','/') or site.port not in (None,443)):
        raise ScorePublicationError('Provide the public HTTPS production site root for readiness verification.')
    response=requests.get(args.site.rstrip('/')+'/api/scoring-status',timeout=(5,15),allow_redirects=False)
    if response.status_code!=200:
        raise ScorePublicationError('Deploy the updated scoring UI and reader configuration before publishing.')
    status=response.json()
    if (status.get('supported_formula')!='us-official-cluster-v1' or status.get('regional_policy')!='exclude'
        or status.get('schema_ready') is not True):
        raise ScorePublicationError('Production UI or scoring schema is not ready. No scores published.')
    plan=json.loads(Path(args.preview).read_text());config=config_file()
    with connect(config) as c:check(c)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:
        url=URL.create('postgresql+psycopg',username=config['user'],password=config['password'],host=config['host'],
            port=int(config['port']),database=config['dbname'],query={'sslmode':'verify-full','sslrootcert':str(CA)})
        publisher=OfficialScorePublisher(url)
        try:
            result=publisher.publish(plan);json.dump(result,f,indent=2);f.write('\n')
            print('Official score publication committed:',json.dumps(result,sort_keys=True))
        finally:
            if publisher.history.last:print('Publication attempt run ID:',publisher.history.last)
            publisher.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('setup');sub.add_parser('check')
    s=sub.add_parser('publish');s.add_argument('--preview',required=True);s.add_argument('--output',required=True)
    s.add_argument('--site',required=True,help='Public HTTPS production root; must expose the new scoring readiness endpoint.')
    s.add_argument('--write',action='store_true',required=True)
    try:
        args=p.parse_args()
        if args.command=='setup':setup()
        elif args.command=='check':
            with connect(config_file()) as c:check(c)
            print('Publisher TLS, identity and column-scoped permissions verified. No writes performed.')
        else:publish(args)
    except Exception as error:
        from safetrip.persistence.postgres import ScorePublicationError
        detail=str(error) if isinstance(error,ScorePublicationError) else type(error).__name__
        print('Official score command failed:',detail,'(connection details suppressed). Check the run ledger before retrying.')
        raise SystemExit(1)
