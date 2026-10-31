
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import DATABASE_URL
from app.db.base import Base
from app.models.celestial_event import CelestialEvent
from app.models.visibility_assessment import VisibilityAssessment
from app.models.environmental_observation import EnvironmentalObservation
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.refresh_token import RefreshToken

# Alembic configuration
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Make SQLAlchemy models visible to Alembic
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""
    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
