"""Append verified UK warning references using the restricted hosted writer.

Default is read-only preview; --write explicitly commits the references.
Does not fetch sources, retrain models, change source versions or public scores.
"""
import argparse
import json
from pathlib import Path
from hosted_advisories import read_config,CA


def run(args):
    from sqlalchemy import create_engine,text
    from sqlalchemy.engine import URL
    from safetrip.ingestion.uk_warning_areas import checked_references
    from safetrip.persistence.warning_areas import store_warning_excerpts
    from safetrip.persistence.postgres import PostgresPublisher
    config=read_config()
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:
        url=URL.create('postgresql+psycopg',username=config['user'],password=config['password'],
            host=config['host'],port=int(config['port']),database=config['dbname'],
            query={'sslmode':'verify-full','sslrootcert':str(CA)})
        engine=create_engine(url,hide_parameters=True,connect_args={'connect_timeout':15,'options':'-c statement_timeout=30000'})
        try:
            report={'database_written':args.write,'versions_examined':0,'versions_with_excerpts':0,
                    'warning_paragraphs':0,'fallback_versions':[],'public_scores_changed':False}
            with engine.begin() as c:
                if not args.write:c.execute(text('SET TRANSACTION READ ONLY'))
                if c.execute(text('SELECT current_user')).scalar_one()!='safetrip_writer':
                    raise ValueError('Unexpected writer identity')
                if args.write:PostgresPublisher._lock(c)
                versions=c.execute(text("""SELECT version_id,raw_payload,source_url FROM advisory.versions
                    WHERE source='uk_fcdo' AND uk_alert_status && ARRAY[
                    'avoid_all_travel_to_parts','avoid_all_but_essential_travel_to_parts']::text[]""")).mappings().all()
                for row in versions:
                    report['versions_examined']+=1
                    raw=bytes(row['raw_payload'])
                    stored={r['paragraph_index']:{'heading':r['heading'],'text':r['body']} for r in c.execute(text("""
                        SELECT paragraph_index,heading,body FROM advisory.paragraphs
                        WHERE version_id=:v AND section_slug='warnings-and-insurance'
                    """),{'v':row['version_id']}).mappings()}
                    references=checked_references(raw,stored)
                    if references:
                        report['versions_with_excerpts']+=1;report['warning_paragraphs']+=len(references)
                    else:report['fallback_versions'].append({'version_id':str(row['version_id']),'source_url':row['source_url']})
                    if args.write:store_warning_excerpts(c,row['version_id'],raw)
            json.dump(report,f,indent=2);f.write('\n')
            print(json.dumps(report,indent=2))
        finally:engine.dispose()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--write',action='store_true')
    try:run(p.parse_args())
    except Exception as e:
        print('Warning-area backfill failed:',type(e).__name__,'(connection details suppressed). Output alone does not prove a commit.')
        raise SystemExit(1)
