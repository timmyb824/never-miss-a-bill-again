"""Auto-migration utilities for running Alembic migrations programmatically."""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

# Suppress Alembic logging globally
logging.getLogger("alembic").setLevel(logging.CRITICAL)
logging.getLogger("alembic.runtime.migration").setLevel(logging.CRITICAL)


def get_alembic_config() -> Config:
    """Get Alembic config with proper paths."""
    # Get the project root (where alembic.ini is located)
    project_root = Path(__file__).parent.parent.parent
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

    # Create Alembic config
    alembic_cfg = Config(str(alembic_ini_path))

    # Disable logging output
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    alembic_cfg.attributes["configure_logger"] = False

    # Override the sqlalchemy.url to use the user's database path
    from nmba.data.database import SQLALCHEMY_DATABASE_URL

    alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)

    return alembic_cfg


def run_migrations() -> None:  # sourcery skip: extract-method
    """Run all pending Alembic migrations to bring database up to date."""
    try:
        alembic_cfg = get_alembic_config()

        # Suppress Alembic output to avoid cluttering the CLI
        import logging

        logging.getLogger("alembic").setLevel(logging.CRITICAL)
        logging.getLogger("alembic.runtime.migration").setLevel(logging.CRITICAL)

        # Check if alembic_version table exists
        from sqlalchemy import create_engine, inspect, text

        from nmba.data.database import SQLALCHEMY_DATABASE_URL

        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        inspector = inspect(engine)

        if "alembic_version" not in inspector.get_table_names():
            # Database exists but has no version tracking
            # Stamp it with the version before our new migration
            command.stamp(
                alembic_cfg, "db6b542a7134"
            )  # Version before unique constraint removal

        # Upgrade to the latest revision
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        # If migrations fail, we don't want to crash the app
        # Log the error but continue (the app might still work)
        # Only show error in debug mode to avoid cluttering output
        import os

        if os.getenv("DEBUG"):
            print(f"Warning: Failed to run database migrations: {e}")
