"""Scoped, plan-checked atomic publication; BERT and clustering inputs are immutable."""
import re
from datetime import datetime,timezone
from .history import RunHistory,encode
from .postgres import PostgresPublisher,ScorePublicationError


class OfficialScorePublisher:
    def __init__(self,url):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        from sqlalchemy.pool import NullPool
        parsed=make_url(url)
        local=parsed.username=='safetrip_score_publisher' and parsed.host in {'localhost','127.0.0.1'}
        hosted=(parsed.host and parsed.host.endswith('.pooler.supabase.com') and parsed.port==5432
                and parsed.query.get('sslmode')=='verify-full'
                and re.fullmatch(r'safetrip_score_publisher\.[a-z0-9]+',parsed.username or ''))
        if (parsed.drivername!='postgresql+psycopg' or not (local or hosted)
            or {'user','password','host','port','dbname','service'} & parsed.query.keys()):
            raise ValueError('An explicit scoped score-publisher account is required.')
        self.engine=create_engine(parsed,poolclass=NullPool,hide_parameters=True,isolation_level='SERIALIZABLE',
            connect_args={'connect_timeout':15,'options':'-c statement_timeout=30000'})
        self.history=RunHistory(self.engine)

    def publish(self,plan):
        from sqlalchemy import text
        from safetrip.scoring.snapshot import COUNTRIES_SQL,PUBLISHED_SQL,ADVISORIES_SQL,snapshot_hash,calculate
        from safetrip.scoring.official import FORMULA_VERSION
        if set(plan.get('previews',{}))!={'exclude'}:
            raise ScorePublicationError('Publication requires a single-policy regional-exclusion preview.')
        if plan.get('database_written') is not False or not plan.get('input_sha256'):
            raise ScorePublicationError('Expected a completed read-only scoring preview.')
        expected=plan['previews']['exclude']
        if expected.get('formula_version')!=FORMULA_VERSION or expected.get('regional_policy')!='exclude':
            raise ScorePublicationError('Preview formula or regional policy does not match the approved rule.')
        self.history.start('publish-official-scores')
        try:
            self.history.record_input({'approved_input_sha256':plan['input_sha256']},
                {'scoring_version':FORMULA_VERSION,'regional_policy':'exclude'})
            with self.engine.begin() as c:
                if c.execute(text('SELECT current_user')).scalar_one()!='safetrip_score_publisher':
                    raise ScorePublicationError('Unexpected effective publisher identity.')
                PostgresPublisher._lock(c)
                # Serializable input snapshot plus the shared pipeline lock.
                # Conflicting external updates abort without broad table grants.
                c.execute(text("SET LOCAL lock_timeout='5s'"))
                snapshot={key:[dict(r) for r in c.execute(text(query)).mappings()] for key,query in [
                    ('countries',COUNTRIES_SQL),('published_scores',PUBLISHED_SQL),('official_us_advisories',ADVISORIES_SQL)]}
                if snapshot_hash(snapshot)!=plan['input_sha256']:
                    raise ScorePublicationError('Stored inputs changed after preview. Generate and review a fresh preview.')
                artifact=calculate(snapshot)
                if not artifact['scores'] or artifact['review_required']:
                    raise ScorePublicationError('Empty catalogue or conflicting US levels require review.')
                if encode(artifact)!=encode(expected):
                    raise ScorePublicationError('Calculated results differ from the reviewed preview.')
                stamp=datetime.now(timezone.utc)
                run=self.history.active
                for row in artifact['scores']:
                    params={'iso3':row['iso3'],'score':row['safe_trip_score'],
                        'level':row['official_us_level'],'us_component':row['official_us_component'],
                        'cluster_component':row['clustering_component'],'formula':FORMULA_VERSION,
                        'run':run,'stamp':stamp,'inputs':encode(row)}
                    c.execute(text('''INSERT INTO public.official_score_history
                        (run_id,iso3,safe_trip_score,scoring_version,inputs)
                        VALUES (:run,:iso3,:score,:formula,CAST(:inputs AS jsonb))'''),params)
                    c.execute(text('''INSERT INTO public.scores
                        (iso3,safe_trip_score,official_us_level,official_us_component,clustering_component,
                         scoring_version,score_run_id,score_published_at)
                        VALUES (:iso3,:score,:level,:us_component,:cluster_component,:formula,:run,:stamp)
                        ON CONFLICT(iso3) DO UPDATE SET safe_trip_score=EXCLUDED.safe_trip_score,
                        official_us_level=EXCLUDED.official_us_level,official_us_component=EXCLUDED.official_us_component,
                        clustering_component=EXCLUDED.clustering_component,scoring_version=EXCLUDED.scoring_version,
                        score_run_id=EXCLUDED.score_run_id,score_published_at=EXCLUDED.score_published_at'''),params)
                c.execute(text('''UPDATE public.pipeline_runs SET input_payload=CAST(:snapshot AS jsonb),
                    input_sha256=:digest,metadata=CAST(:metadata AS jsonb) WHERE run_id=:run'''),
                    {'snapshot':encode(snapshot),'digest':plan['input_sha256'],'run':run,
                     'metadata':encode({'scoring_version':FORMULA_VERSION,'regional_policy':'exclude',
                        'nominal_weights':artifact['nominal_weights'],'missing_policy':artifact['missing_policy'],
                        'clustering_source':artifact['clustering_source']})})
                self.history.succeeded(c,artifact['coverage'],len(artifact['scores']))
            self.history.committed()
            return {'run_id':str(self.history.last),'scoring_version':FORMULA_VERSION,
                    'regional_policy':'exclude','published_rows':len(artifact['scores']),
                    'changed_countries':artifact['changed_countries'],'input_sha256':plan['input_sha256'],
                    'coverage':artifact['coverage'],'database_written':True}
        except BaseException as error:
            self.history.failed(error)
            raise

    def close(self):self.engine.dispose()
