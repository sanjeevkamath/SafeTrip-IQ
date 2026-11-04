"""Rehearse the bridge in a fresh disposable Docker Postgres, never Supabase.

Uses synthetic credentials only on a temporary localhost-bound container, no real
credentials, and removes the container/volume on exit. Requires database venv.
"""
import json
import subprocess
import time
import uuid

from build_hosted_advisories import ROOT, migration_sql, render


def main():
    import psycopg
    from safetrip.persistence.advisories import ingest_capture
    from safetrip.persistence.postgres import PostgresPublisher
    from hosted_advisories import enable_writer
    from hosted_reader import enable_reader, check_reader_grants

    target = 'safetrip-hosted-rehearsal-' + uuid.uuid4().hex[:8]
    def docker(*args, input=None, check=True):
        return subprocess.run(['docker',*args], input=input, text=True,
                              capture_output=True, check=check)
    def sql(statement, check=True):
        return docker('exec','-i',target,'psql','-U','postgres','-d','postgres',
                      '-X','-v','ON_ERROR_STOP=1','-At', input=statement,check=check)
    docker('run','--rm','-d','--name',target,'-p','127.0.0.1::5432',
           '-e','POSTGRES_PASSWORD=rehearsal_local_only','postgres:17.11-bookworm')
    try:
        for _ in range(60):
            if docker('exec',target,'pg_isready','-U','postgres',check=False).returncode==0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('Disposable database did not start')
        # Match the audited legacy table definitions; model Supabase default API grants.
        legacy=migration_sql('0001_application_schema.py').split('REVOKE ALL ON public.countries')[0]
        sql("""CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
            CREATE ROLE service_role NOLOGIN BYPASSRLS;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon,authenticated,service_role;
            """ + legacy + """
            INSERT INTO countries(iso3,name) VALUES ('CAN','Canada'),('JPN','Japan'),('ATA','Antarctica'),('PSE','Palestine');
            INSERT INTO scores(iso3,safe_trip_score) VALUES ('CAN',10);
            """ + '\n'.join(f'ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;' for t in
                ['countries','culture','scores','bert_scores','clustering','travel_advisories']))
        script=ROOT/'db/hosted/001_advisory_foundation.sql'
        assert script.read_text()==render(), 'Generated migration is stale'
        sql(script.read_text())
        assert sql('SELECT count(*) FROM countries').stdout.strip()=='5'
        assert sql("SELECT safe_trip_score FROM scores WHERE iso3='CAN'").stdout.strip()=='10'
        assert sql("SELECT rolcanlogin FROM pg_roles WHERE rolname='safetrip_writer'").stdout.strip()=='f'
        # Confirm incompatible/rerun installation fails instead of silently stamping.
        assert sql(script.read_text(),check=False).returncode!=0
        # Login is enabled ONLY in the disposable rehearsal for a real worker import.
        port=int(docker('port',target,'5432/tcp').stdout.strip().rsplit(':',1)[1])
        with psycopg.connect(host='127.0.0.1',port=port,dbname='postgres',user='postgres',password='rehearsal_local_only') as owner:
            enable_writer(owner,'writer_local_only')
            enable_reader(owner,'reader_local_only')
        publisher=PostgresPublisher(f'postgresql+psycopg://safetrip_writer:writer_local_only@127.0.0.1:{port}/postgres')
        try:
            bundle=json.loads((ROOT/'tests/fixtures/us_uk_capture.json').read_text())
            first=ingest_capture(publisher,bundle)
            second=ingest_capture(publisher,bundle)
            assert first['storage']['new_versions']==4
            assert second['storage']['new_versions']==0
        finally:
            publisher.close()
        with psycopg.connect(host='127.0.0.1',port=port,dbname='postgres',user='safetrip_reader',password='reader_local_only') as c:
            # Regression: the original checker failed on name resolution even
            # though denying the reader private-schema USAGE was intentional.
            try:
                with c.transaction():
                    c.execute("SELECT has_table_privilege(current_user,'advisory.versions','SELECT')")
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError('Expected private-schema name lookup to be denied')
            assert check_reader_grants(c)==4
            assert c.execute('SELECT count(*) FROM public.advisory_summaries').fetchone()[0]==4
            assert c.execute('SELECT count(*) FROM countries').fetchone()[0]==5
            for statement in ['SELECT * FROM advisory.versions','SELECT * FROM public.raw_feeds',
                              'UPDATE public.scores SET safe_trip_score=0 WHERE false']:
                try:
                    with c.transaction():
                        c.execute(statement)
                except psycopg.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError('Reader boundary failed')
        assert sql("SELECT safe_trip_score FROM scores WHERE iso3='CAN'").stdout.strip()=='10'
        assert sql('SET ROLE safetrip_writer; UPDATE scores SET safe_trip_score=0 WHERE false;',check=False).returncode!=0
        print('PASS: additive install, default API grant removal, NOLOGIN roles, real ingestion/replay, reader isolation, score preservation, rerun refusal.')
    finally:
        docker('rm','-f','-v',target,check=False)


if __name__=='__main__':
    main()
