"""Retain original feed bytes independently of publication success."""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE public.raw_feeds (
            run_id uuid PRIMARY KEY REFERENCES public.pipeline_runs(run_id),
            fetched_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            sha256 text NOT NULL,
            content bytea NOT NULL
        );
        ALTER TABLE public.raw_feeds ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.raw_feeds FROM PUBLIC, safetrip_reader, safetrip_writer;
        GRANT SELECT, INSERT ON public.raw_feeds TO safetrip_writer;
        CREATE POLICY raw_read ON public.raw_feeds FOR SELECT TO safetrip_writer USING (true);
        CREATE POLICY raw_insert ON public.raw_feeds FOR INSERT TO safetrip_writer WITH CHECK (true);
    """)


def downgrade():
    op.execute("DROP TABLE public.raw_feeds")
