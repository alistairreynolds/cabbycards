import asyncio
import os
from datetime import datetime
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrations only need the DB URL, not the full app config — load .env if present
# and read DATABASE_URL directly so a migration run doesn't require every setting.
load_dotenv()
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

target_metadata = Base.metadata


def _stamp_revision_id(context_, revision, directives) -> None:
    """Give every new revision a sortable timestamp id, so migrations order
    chronologically rather than by opaque hex.

    The id uses underscores (Alembic disallows '-' in rev ids); the *filename*
    uses hyphens via file_template in alembic.ini.
    """
    if not directives:
        return
    directives[0].rev_id = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=_stamp_revision_id,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=_stamp_revision_id,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
