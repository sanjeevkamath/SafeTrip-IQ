"""Expose only provenance-linked official UK regional warning excerpts."""
from alembic import op

revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""
        CREATE TABLE advisory.warning_excerpts (
            version_id uuid NOT NULL,
            extractor_version text NOT NULL CHECK (length(btrim(extractor_version))>0),
            section_slug text NOT NULL CHECK (section_slug='warnings-and-insurance'),
            paragraph_index integer NOT NULL,
            warning_heading text NOT NULL CHECK (length(btrim(warning_heading))>0),
            PRIMARY KEY(version_id,extractor_version,section_slug,paragraph_index),
            FOREIGN KEY(version_id,section_slug,paragraph_index)
                REFERENCES advisory.paragraphs(version_id,section_slug,paragraph_index)
        );
        ALTER TABLE advisory.warning_excerpts ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON advisory.warning_excerpts FROM PUBLIC,safetrip_reader,safetrip_writer;
        GRANT SELECT,INSERT ON advisory.warning_excerpts TO safetrip_writer;
        CREATE POLICY warning_excerpt_read ON advisory.warning_excerpts FOR SELECT TO safetrip_writer USING(true);
        CREATE POLICY warning_excerpt_insert ON advisory.warning_excerpts FOR INSERT TO safetrip_writer WITH CHECK(true);
        CREATE VIEW public.advisory_warning_excerpts AS
        SELECT DISTINCT s.iso3,s.version_id,w.extractor_version,w.section_slug,w.paragraph_index,
               w.warning_heading,p.heading,p.body
        FROM public.advisory_summaries s
        JOIN advisory.warning_excerpts w ON w.version_id=s.version_id
        JOIN advisory.paragraphs p ON p.version_id=w.version_id
            AND p.section_slug=w.section_slug AND p.paragraph_index=w.paragraph_index
        WHERE s.source='uk_fcdo' AND w.extractor_version='uk-warning-areas-v1'
            AND s.uk_alert_status && ARRAY['avoid_all_travel_to_parts','avoid_all_but_essential_travel_to_parts']::text[];
        REVOKE ALL ON public.advisory_warning_excerpts FROM PUBLIC,safetrip_reader,safetrip_writer;
        GRANT SELECT ON public.advisory_warning_excerpts TO safetrip_reader;
    """)


def downgrade():
    op.execute('DROP VIEW public.advisory_warning_excerpts')
    op.execute('DROP TABLE advisory.warning_excerpts')
