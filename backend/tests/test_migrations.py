"""Migration behaviour.

These guard the schema that production actually runs. The model tests assert
what the ORM believes; these assert that the migrations build the same thing
and can be rolled back cleanly.
"""

import pytest
from sqlalchemy import Engine, inspect

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.db.base import Base
from tests.db_fixtures import (
    TEST_DATABASE_SUFFIX,
    _alembic_config,
    _require_test_database,
    _test_database_url,
)


def test_migrations_produce_a_schema_matching_the_models(db_engine: Engine) -> None:
    """Autogenerate must detect nothing to do against the migrated schema.

    This is the check that stops the two definitions drifting: if someone edits
    a model without writing a migration, production would end up with a schema
    the code does not expect, and every other test would still pass because the
    fixtures migrate from the same stale files.
    """
    with db_engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_type": True, "compare_server_default": True},
        )
        differences = compare_metadata(context, Base.metadata)

    assert differences == [], f"Models and migrations have drifted: {differences}"


def test_downgrade_then_upgrade_round_trips(db_engine: Engine) -> None:
    """A full rollback must leave nothing behind that blocks re-applying.

    Postgres keeps an enum type alive after its last table is dropped, so a
    downgrade that forgets to drop `user_role` fails the next upgrade with
    "type already exists" — a rollback that cannot be undone.
    """
    config = _alembic_config(_test_database_url())

    command.downgrade(config, "base")
    assert "users" not in inspect(db_engine).get_table_names()

    command.upgrade(config, "head")
    assert "users" in inspect(db_engine).get_table_names()


def test_refuses_to_run_against_a_non_test_database() -> None:
    """The schema-dropping fixture must never accept the development database.

    `db_engine` drops the whole public schema, so a mistyped TEST_DATABASE_URL
    would destroy real data. The suffix check is the only thing standing
    between that mistake and an empty database.
    """
    development_url = "postgresql+psycopg://jobportal:jobportal@localhost:5432/jobportal"

    with pytest.raises(RuntimeError, match=TEST_DATABASE_SUFFIX):
        _require_test_database(development_url)


def test_accepts_a_test_database_url() -> None:
    """The guard must not reject a correctly-named test database."""
    _require_test_database(
        f"postgresql+psycopg://jobportal:jobportal@localhost:5432/"
        f"jobportal{TEST_DATABASE_SUFFIX}"
    )
