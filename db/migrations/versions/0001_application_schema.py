"""Preserve the captured application schema with portable restricted roles.

Source: Phase 0 public-schema backup, 2026-10-07. Supabase extensions,
API roles, and grants are deliberately not copied. Provision the three
safetrip roles before applying this revision to an EMPTY database.
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ("countries", "culture", "scores", "bert_scores", "clustering", "travel_advisories")
PUBLIC_TABLES = ("countries", "culture", "scores")


def upgrade():
    op.execute("""
        CREATE TABLE public.countries (
            iso3 text PRIMARY KEY, name text NOT NULL, continent text,
            flag_url text, iso2 varchar(2)
        );
        CREATE INDEX idx_countries_iso2 ON public.countries (iso2);
        CREATE TABLE public.culture (
            iso3 text PRIMARY KEY REFERENCES public.countries(iso3),
            language text, greeting text, currency text, overview text,
            cities text, etiquette text, religion text, dos text, donts text,
            food text, cultural_safety_notes text
        );
        CREATE TABLE public.scores (
            iso3 char(3) PRIMARY KEY, safe_trip_score real,
            bert_score integer, clustering_score integer
        );
        CREATE TABLE public.bert_scores (
            iso3 text PRIMARY KEY REFERENCES public.countries(iso3),
            cleaned_text text, bert_score integer
        );
        CREATE TABLE public.clustering (
            iso3 text PRIMARY KEY REFERENCES public.countries(iso3),
            clustering_score integer, ppi double precision,
            gpi double precision, gti double precision, pvi double precision
        );
        CREATE TABLE public.travel_advisories (
            iso3 char(3) PRIMARY KEY, country_name text, country_code text,
            pub_date_raw text, description_raw_html text, description_text text,
            last_fetched_at timestamptz DEFAULT now()
        );
    """)
    for table in TABLES:
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC, safetrip_reader, safetrip_writer")
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table} TO safetrip_writer")
        op.execute(f"CREATE POLICY worker_access ON public.{table} TO safetrip_writer USING (true) WITH CHECK (true)")
    for table in PUBLIC_TABLES:
        op.execute(f"GRANT SELECT ON public.{table} TO safetrip_reader")
        op.execute(f"CREATE POLICY web_read ON public.{table} FOR SELECT TO safetrip_reader USING (true)")


def downgrade():
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE public.{table}")
