"""Add private, source-versioned advisory storage without changing public scores."""
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

TABLES = ('documents', 'versions', 'coverage', 'observations', 'paragraphs', 'analyses', 'evidence')


def upgrade():
    op.execute("""
        CREATE SCHEMA advisory;
        REVOKE ALL ON SCHEMA advisory FROM PUBLIC, safetrip_reader, safetrip_writer;
        GRANT USAGE ON SCHEMA advisory TO safetrip_writer;
        ALTER DEFAULT PRIVILEGES IN SCHEMA advisory REVOKE ALL ON TABLES FROM PUBLIC;
        ALTER DEFAULT PRIVILEGES IN SCHEMA advisory REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

        CREATE TABLE advisory.documents (
            document_id uuid PRIMARY KEY,
            source text NOT NULL CHECK (source IN ('us_state', 'uk_fcdo')),
            source_key text NOT NULL CHECK (length(btrim(source_key)) > 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source, source_key),
            UNIQUE (document_id, source)
        );

        CREATE TABLE advisory.versions (
            version_id uuid PRIMARY KEY,
            document_id uuid NOT NULL,
            source text NOT NULL,
            parser_version text NOT NULL CHECK (length(btrim(parser_version)) > 0),
            content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            raw_payload bytea NOT NULL CHECK (octet_length(raw_payload) > 0),
            source_url text NOT NULL CHECK (source_url ~ '^https://'),
            source_public_updated_at timestamptz,
            source_updated_at timestamptz,
            source_reviewed_at timestamptz,
            us_level smallint,
            uk_alert_status text[],
            metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
            created_at timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (document_id, source) REFERENCES advisory.documents(document_id, source),
            UNIQUE (document_id, content_sha256, parser_version),
            UNIQUE (version_id, document_id),
            CHECK (content_sha256 = encode(sha256(raw_payload), 'hex')),
            CHECK (
                (source = 'us_state' AND us_level IS NOT NULL AND us_level BETWEEN 1 AND 4
                    AND uk_alert_status IS NULL)
                OR
                (source = 'uk_fcdo' AND us_level IS NULL AND uk_alert_status IS NOT NULL
                    AND array_position(uk_alert_status, NULL) IS NULL
                    AND uk_alert_status <@ ARRAY[
                        'avoid_all_travel_to_whole_country',
                        'avoid_all_but_essential_travel_to_whole_country',
                        'avoid_all_travel_to_parts',
                        'avoid_all_but_essential_travel_to_parts'
                    ]::text[])
            )
        );

        -- Document coverage is distinct from the geographic scope of a warning.
        CREATE TABLE advisory.coverage (
            coverage_id uuid PRIMARY KEY,
            version_id uuid NOT NULL REFERENCES advisory.versions(version_id),
            iso3 text REFERENCES public.countries(iso3),
            scope text NOT NULL CHECK (scope IN ('whole_country', 'parts', 'unresolved')),
            region_label text,
            CHECK (
                (scope = 'whole_country' AND iso3 IS NOT NULL AND region_label IS NULL)
                OR (scope = 'parts' AND iso3 IS NOT NULL AND length(btrim(region_label)) > 0)
                OR (scope = 'unresolved' AND length(btrim(region_label)) > 0)
            ),
            CHECK (scope = 'whole_country' OR region_label IS NOT NULL)
        );
        CREATE UNIQUE INDEX advisory_coverage_unique ON advisory.coverage
            (version_id, coalesce(iso3, ''), scope, coalesce(region_label, ''));
        CREATE INDEX advisory_coverage_country ON advisory.coverage (iso3);

        -- Seeing identical content again records freshness without duplicating a version.
        CREATE TABLE advisory.observations (
            run_id uuid NOT NULL REFERENCES public.pipeline_runs(run_id),
            document_id uuid NOT NULL REFERENCES advisory.documents(document_id),
            version_id uuid NOT NULL,
            fetched_at timestamptz NOT NULL,
            PRIMARY KEY (run_id, document_id),
            FOREIGN KEY (version_id, document_id) REFERENCES advisory.versions(version_id, document_id)
        );
        CREATE INDEX advisory_observations_freshness ON advisory.observations
            (document_id, fetched_at DESC);

        CREATE TABLE advisory.paragraphs (
            version_id uuid NOT NULL REFERENCES advisory.versions(version_id),
            section_slug text NOT NULL CHECK (length(btrim(section_slug)) > 0),
            paragraph_index integer NOT NULL CHECK (paragraph_index >= 0),
            section_title text NOT NULL,
            heading text,
            body text NOT NULL CHECK (length(btrim(body)) > 0),
            PRIMARY KEY (version_id, section_slug, paragraph_index)
        );

        -- Experimental outputs have no permission or path into public scores.
        CREATE TABLE advisory.analyses (
            analysis_id uuid PRIMARY KEY,
            version_id uuid NOT NULL REFERENCES advisory.versions(version_id),
            run_id uuid NOT NULL REFERENCES public.pipeline_runs(run_id),
            analyzer_version text NOT NULL CHECK (length(btrim(analyzer_version)) > 0),
            input_sha256 text NOT NULL CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
            metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (version_id, analyzer_version, input_sha256),
            UNIQUE (analysis_id, version_id)
        );
        CREATE TABLE advisory.evidence (
            analysis_id uuid NOT NULL,
            version_id uuid NOT NULL,
            section_slug text NOT NULL,
            paragraph_index integer NOT NULL,
            category text NOT NULL CHECK (category IN (
                'crime', 'kidnapping', 'terrorism', 'conflict_unrest', 'health',
                'natural_hazards', 'transport', 'legal_restrictions'
            )),
            context text NOT NULL DEFAULT 'unreviewed' CHECK (context IN (
                'unreviewed', 'destination_specific', 'generic', 'historical', 'third_region', 'negated'
            )),
            PRIMARY KEY (analysis_id, section_slug, paragraph_index, category),
            FOREIGN KEY (analysis_id, version_id) REFERENCES advisory.analyses(analysis_id, version_id),
            FOREIGN KEY (version_id, section_slug, paragraph_index)
                REFERENCES advisory.paragraphs(version_id, section_slug, paragraph_index)
        );
    """)
    for table in TABLES:
        op.execute(f"ALTER TABLE advisory.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON advisory.{table} FROM PUBLIC, safetrip_reader, safetrip_writer")
        op.execute(f"GRANT SELECT, INSERT ON advisory.{table} TO safetrip_writer")
        op.execute(f"CREATE POLICY worker_read ON advisory.{table} FOR SELECT TO safetrip_writer USING (true)")
        op.execute(f"CREATE POLICY worker_insert ON advisory.{table} FOR INSERT TO safetrip_writer WITH CHECK (true)")


def downgrade():
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE advisory.{table}")
    op.execute('DROP SCHEMA advisory')
