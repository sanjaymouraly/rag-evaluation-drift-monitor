"""The alembic migration must produce exactly the schema the ORM expects."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app import models  # noqa: F401  (register the mappers)
from app.db import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("migrations") / "migrated.db"
    env = {**os.environ, "RQM_DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    return db_path


def test_migration_creates_every_model_table(migrated_db):
    engine = create_engine(f"sqlite:///{migrated_db}")
    inspector = inspect(engine)
    migrated = set(inspector.get_table_names()) - {"alembic_version"}
    expected = set(Base.metadata.tables)
    assert expected <= migrated, f"missing tables: {sorted(expected - migrated)}"


def test_migration_columns_match_the_models(migrated_db):
    engine = create_engine(f"sqlite:///{migrated_db}")
    inspector = inspect(engine)
    for table_name, table in Base.metadata.tables.items():
        migrated_columns = {c["name"] for c in inspector.get_columns(table_name)}
        model_columns = {c.name for c in table.columns}
        assert model_columns <= migrated_columns, (
            f"table {table_name} is missing columns {sorted(model_columns - migrated_columns)}"
        )


def test_migration_can_be_downgraded(migrated_db):
    env = {**os.environ, "RQM_DATABASE_URL": f"sqlite:///{migrated_db}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(f"sqlite:///{migrated_db}")
    inspector = inspect(engine)
    remaining = set(inspector.get_table_names()) - {"alembic_version"}
    assert not remaining, f"tables left after downgrade: {sorted(remaining)}"
