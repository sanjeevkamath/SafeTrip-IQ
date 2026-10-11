"""Record pipeline attempts and preserve the inputs behind published scores."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE public.pipeline_runs (
            run_id uuid PRIMARY KEY,
            command text NOT NULL,
            status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            metadata jsonb NOT NULL DEFAULT '{}',
            input_sha256 text,
            input_payload jsonb,
            coverage jsonb,
            published_rows integer NOT NULL DEFAULT 0,
            error_type text,
            CHECK ((status = 'running') = (finished_at IS NULL))
        );
        CREATE INDEX pipeline_runs_started_at_idx ON public.pipeline_runs (started_at DESC);
        CREATE TABLE public.score_history (
            run_id uuid NOT NULL REFERENCES public.pipeline_runs(run_id),
            iso3 text NOT NULL,
            safe_trip_score real,
            bert_score integer,
            clustering_score integer,
            scoring_version text NOT NULL,
            inputs jsonb NOT NULL,
            PRIMARY KEY (run_id, iso3)
        );
        ALTER TABLE public.scores ADD COLUMN last_run_id uuid REFERENCES public.pipeline_runs(run_id);
        ALTER TABLE public.scores ADD COLUMN published_at timestamptz;
        ALTER TABLE public.bert_scores ADD COLUMN last_run_id uuid REFERENCES public.pipeline_runs(run_id);
        ALTER TABLE public.clustering ADD COLUMN last_run_id uuid REFERENCES public.pipeline_runs(run_id);
        ALTER TABLE public.travel_advisories ADD COLUMN last_run_id uuid REFERENCES public.pipeline_runs(run_id);
        ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.score_history ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.pipeline_runs, public.score_history FROM PUBLIC, safetrip_reader, safetrip_writer;
        GRANT SELECT, INSERT, UPDATE ON public.pipeline_runs TO safetrip_writer;
        GRANT SELECT, INSERT ON public.score_history TO safetrip_writer;
        CREATE POLICY worker_runs ON public.pipeline_runs TO safetrip_writer USING (true) WITH CHECK (true);
        CREATE POLICY history_read ON public.score_history FOR SELECT TO safetrip_writer USING (true);
        CREATE POLICY history_insert ON public.score_history FOR INSERT TO safetrip_writer WITH CHECK (true);
    """)


def downgrade():
    for table in ("travel_advisories", "clustering", "bert_scores", "scores"):
        op.execute(f"ALTER TABLE public.{table} DROP COLUMN last_run_id")
    op.execute("ALTER TABLE public.scores DROP COLUMN published_at")
    op.execute("DROP TABLE public.score_history")
    op.execute("DROP TABLE public.pipeline_runs")
