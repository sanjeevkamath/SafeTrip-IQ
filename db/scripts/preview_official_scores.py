"""Read-only scoring comparison. Never publishes or uses backend write credentials."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from hosted_reader import connect,read_config,check_reader


def run(args):
    from psycopg import IsolationLevel
    from psycopg.rows import dict_row
    from safetrip.scoring.official import preview_scores
    from safetrip.scoring.snapshot import COUNTRIES_SQL,PUBLISHED_SQL,ADVISORIES_SQL,snapshot_hash
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:
        with connect(read_config()) as c:
            c.isolation_level=IsolationLevel.REPEATABLE_READ
            check_reader(c)  # Sets read_only before beginning the snapshot.
            with c.cursor(row_factory=dict_row) as cur:
                cur.execute(COUNTRIES_SQL);countries=cur.fetchall()
                cur.execute(PUBLISHED_SQL)
                published=cur.fetchall()
                cur.execute(ADVISORIES_SQL);advisories=cur.fetchall()
        snapshot={'countries':countries,'published_scores':published,'official_us_advisories':advisories}
        policies=['exclude','highest'] if args.regional_policy=='compare' else [args.regional_policy]
        report={'created_at':datetime.now(timezone.utc).isoformat(),'database_written':False,
                'input_sha256':snapshot_hash(snapshot),'input_snapshot':snapshot,
                'previews':{policy:preview_scores(countries,{r['iso3'].strip():r for r in published},advisories,policy)
                            for policy in policies}}
        json.dump(report,f,indent=2,default=str);f.write('\n')
        for policy,preview in report['previews'].items():
            print('Regional policy:',policy,'coverage:',json.dumps(preview['coverage'],sort_keys=True),
                  'changed countries:',preview['changed_countries'],'conflicts:',len(preview['review_required']))
        print('Read-only scoring preview saved. No scores, permissions or model outputs changed.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--regional-policy',choices=['compare','exclude','highest'],default='compare')
    try:run(p.parse_args())
    except Exception as e:
        print('Scoring preview failed:',type(e).__name__,'(connection details suppressed). Output alone is not a successful result.')
        raise SystemExit(1)
