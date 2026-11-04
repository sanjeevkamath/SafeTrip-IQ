"""Expose an explicit read-only advisory projection to the website role."""
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    # Owner-rights view is deliberate: the reader cannot access the underlying
    # private schema. Only the reviewed projection below crosses that boundary.
    op.execute("""
        CREATE VIEW public.advisory_summaries AS
        WITH latest AS (
            SELECT DISTINCT ON (o.document_id) o.document_id, o.version_id, o.fetched_at
            FROM advisory.observations o
            JOIN public.pipeline_runs r ON r.run_id = o.run_id
            JOIN advisory.versions v ON v.version_id = o.version_id
            WHERE r.status = 'succeeded'
            ORDER BY o.document_id, o.fetched_at DESC, v.created_at DESC,
                     r.finished_at DESC, o.version_id
        )
        SELECT c.iso3, d.document_id, d.source, v.version_id,
               v.source_url, v.source_public_updated_at, v.source_updated_at,
               v.source_reviewed_at, l.fetched_at, v.us_level, v.uk_alert_status,
               c.scope AS coverage_scope, c.region_label
        FROM latest l
        JOIN advisory.documents d ON d.document_id = l.document_id
        JOIN advisory.versions v ON v.version_id = l.version_id
        JOIN advisory.coverage c ON c.version_id = v.version_id
        WHERE c.iso3 IS NOT NULL AND c.scope <> 'unresolved';
        REVOKE ALL ON public.advisory_summaries FROM PUBLIC, safetrip_writer, safetrip_reader;
        GRANT SELECT ON public.advisory_summaries TO safetrip_reader;
    """)


def downgrade():
    op.execute('DROP VIEW public.advisory_summaries')
