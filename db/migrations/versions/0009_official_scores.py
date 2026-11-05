"""Explicit official score fields and a column-scoped publication role.

Role is provisioned by the local bootstrap or standalone hosted wrapper.
"""
from alembic import op

revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""
        ALTER TABLE public.scores
            ADD COLUMN official_us_level smallint CHECK(official_us_level BETWEEN 1 AND 4),
            ADD COLUMN official_us_component real CHECK(official_us_component BETWEEN 0 AND 10),
            ADD COLUMN clustering_component real CHECK(clustering_component BETWEEN 0 AND 10),
            ADD COLUMN scoring_version text,
            ADD COLUMN score_run_id uuid REFERENCES public.pipeline_runs(run_id),
            ADD COLUMN score_published_at timestamptz;
        CREATE TABLE public.official_score_history (
            run_id uuid NOT NULL REFERENCES public.pipeline_runs(run_id),
            iso3 text NOT NULL REFERENCES public.countries(iso3),
            safe_trip_score real,
            scoring_version text NOT NULL,
            inputs jsonb NOT NULL CHECK(jsonb_typeof(inputs)='object'),
            PRIMARY KEY(run_id,iso3)
        );
        ALTER TABLE public.official_score_history ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.official_score_history FROM PUBLIC,safetrip_reader,safetrip_writer,safetrip_score_publisher;
        GRANT SELECT,INSERT ON public.official_score_history TO safetrip_score_publisher;
        CREATE POLICY scorer_history ON public.official_score_history TO safetrip_score_publisher
            USING(true) WITH CHECK(true);
        GRANT SELECT ON public.countries,public.scores,public.advisory_summaries TO safetrip_score_publisher;
        CREATE POLICY scorer_countries ON public.countries FOR SELECT TO safetrip_score_publisher USING(true);
        CREATE POLICY scorer_read ON public.scores FOR SELECT TO safetrip_score_publisher USING(true);
        GRANT INSERT(iso3,safe_trip_score,official_us_level,official_us_component,clustering_component,
                     scoring_version,score_run_id,score_published_at) ON public.scores TO safetrip_score_publisher;
        GRANT UPDATE(safe_trip_score,official_us_level,official_us_component,clustering_component,
                     scoring_version,score_run_id,score_published_at) ON public.scores TO safetrip_score_publisher;
        CREATE POLICY scorer_insert ON public.scores FOR INSERT TO safetrip_score_publisher WITH CHECK(true);
        CREATE POLICY scorer_update ON public.scores FOR UPDATE TO safetrip_score_publisher USING(true) WITH CHECK(true);
        GRANT SELECT,INSERT,UPDATE ON public.pipeline_runs TO safetrip_score_publisher;
        CREATE POLICY scorer_runs ON public.pipeline_runs TO safetrip_score_publisher
            USING(command='publish-official-scores') WITH CHECK(command='publish-official-scores');
    """)


def downgrade():
    op.execute("""
        DROP POLICY scorer_runs ON public.pipeline_runs;
        REVOKE SELECT,INSERT,UPDATE ON public.pipeline_runs FROM safetrip_score_publisher;
        DROP POLICY scorer_update ON public.scores;
        DROP POLICY scorer_insert ON public.scores;
        DROP POLICY scorer_read ON public.scores;
        DROP POLICY scorer_countries ON public.countries;
        REVOKE SELECT ON public.countries,public.scores,public.advisory_summaries FROM safetrip_score_publisher;
        REVOKE INSERT(iso3,safe_trip_score,official_us_level,official_us_component,clustering_component,
                     scoring_version,score_run_id,score_published_at) ON public.scores FROM safetrip_score_publisher;
        REVOKE UPDATE(safe_trip_score,official_us_level,official_us_component,clustering_component,
                     scoring_version,score_run_id,score_published_at) ON public.scores FROM safetrip_score_publisher;
        DROP TABLE public.official_score_history;
        ALTER TABLE public.scores DROP COLUMN score_published_at,DROP COLUMN score_run_id,
            DROP COLUMN scoring_version,DROP COLUMN clustering_component,
            DROP COLUMN official_us_component,DROP COLUMN official_us_level;
    """)
