"""Expose only a publication timestamp and source kind to the website."""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE public.refresh_status (
            singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
            published_at timestamptz NOT NULL,
            source_kind text NOT NULL CHECK (source_kind IN ('state_department_feed','local_xml','unknown'))
        );
        ALTER TABLE public.refresh_status ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.refresh_status FROM PUBLIC, safetrip_reader, safetrip_writer;
        GRANT SELECT ON public.refresh_status TO safetrip_reader;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.refresh_status TO safetrip_writer;
        CREATE POLICY status_read ON public.refresh_status FOR SELECT TO safetrip_reader USING (true);
        CREATE POLICY status_write ON public.refresh_status TO safetrip_writer USING (true) WITH CHECK (true);
    """)


def downgrade():
    op.execute("DROP TABLE public.refresh_status")
