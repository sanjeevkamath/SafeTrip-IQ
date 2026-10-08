"""Migrations require an explicit URL; never load production .env implicitly."""
import os

from alembic import context
from sqlalchemy import create_engine, pool

url = os.environ.get("SAFETRIP_MIGRATION_URL")
if not url:
    raise RuntimeError("Set SAFETRIP_MIGRATION_URL explicitly before running migrations")

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
