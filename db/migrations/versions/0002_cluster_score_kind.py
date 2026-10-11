"""Distinguish unverified/raw cluster IDs from ranked risk tiers."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Existing data is intentionally unverified; migration cannot infer meaning.
    op.execute("""ALTER TABLE public.clustering ADD COLUMN score_kind text
               NOT NULL DEFAULT 'unverified'
               CHECK (score_kind IN ('unverified', 'raw_cluster_id', 'risk_tier'))""")


def downgrade():
    op.execute("ALTER TABLE public.clustering DROP COLUMN score_kind")
