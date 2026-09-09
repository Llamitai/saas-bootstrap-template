"""Check graph, real upgrades and model drift using exclusively owned databases."""

import argparse
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src.common.settings import settings


def check_migrations(previous: str | None = None, fixture: Path | None = None, assertion: Path | None = None) -> None:
    config = Config("alembic.ini")
    graph = ScriptDirectory.from_config(config)
    heads = graph.get_heads()
    if len(heads) != 1:
        raise ValueError(f"Expected one Alembic head, found {heads}; merge revisions before continuing")
    head = graph.get_revision(heads[0])
    assert head is not None
    prior = previous or head.down_revision or "base"
    if not isinstance(prior, str):
        raise ValueError("A merge head requires --previous <supported-revision>")
    if prior != "base":
        graph.get_revision(prior)  # Fail before allocating resources for an unknown revision.
    if bool(fixture) != bool(assertion):
        raise ValueError("Data evolution requires both --fixture-sql and --assert-sql")
    url = make_url(str(settings.database_url))
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        for phase, start in (("empty", "base"), ("previous", prior)):
            name = f"migration_check_{uuid4().hex}"
            database = create_engine(url.set(database=name))
            created = False
            try:
                with admin.connect() as connection:
                    connection.execute(text(f'CREATE DATABASE "{name}"'))
                    created = True
                with database.connect() as connection:
                    config.attributes["connection"] = connection
                    command.upgrade(config, start)
                    if phase == "previous" and fixture:
                        connection.exec_driver_sql(fixture.read_text())
                        connection.commit()
                    command.upgrade(config, "head")
                    command.check(config)
                    if (
                        phase == "previous"
                        and assertion
                        and connection.exec_driver_sql(assertion.read_text()).scalar_one() is not True
                    ):
                        raise ValueError("Migration data preservation assertion failed")
                print(f"Migration upgrade {start} -> {heads[0]} and model drift check passed")
            finally:
                database.dispose()
                if created:
                    with admin.connect() as connection:
                        connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous")
    parser.add_argument("--fixture-sql", type=Path)
    parser.add_argument("--assert-sql", type=Path)
    args = parser.parse_args()
    check_migrations(args.previous, args.fixture_sql, args.assert_sql)
