"""Alembic online/offline configuration with SQLite batch rendering."""

import os

from alembic import context

from routepilot.shared.db.engine import make_engine

config = context.config
url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
