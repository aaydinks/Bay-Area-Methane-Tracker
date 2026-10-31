"""Shared fixtures for the database tests: a fresh database with the migrations applied.

They run only when ``TEST_DATABASE_URL`` names an admin connection to a scratch PostGIS
database (CI provides a container); otherwise every test in this folder is skipped.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.conninfo import make_conninfo  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
ADMIN_DSN = os.environ.get("TEST_DATABASE_URL")
TEST_DB = "methanewatch_migrations_test"


HERE = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items):
    """Mark the tests in this folder ``db`` and skip them without a database."""
    for item in items:
        if HERE not in Path(str(item.path)).resolve().parents:
            continue
        item.add_marker(pytest.mark.db)
        if not ADMIN_DSN:
            item.add_marker(pytest.mark.skip(reason="TEST_DATABASE_URL is not set"))


def run_script(conn, sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)


@pytest.fixture(scope="session")
def test_dsn() -> str:
    """A fresh database with the migrations applied, dropped again at the end."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        admin.execute(f"drop database if exists {TEST_DB} with (force)")
        admin.execute(f"create database {TEST_DB}")
    dsn = make_conninfo(ADMIN_DSN, dbname=TEST_DB)
    with psycopg.connect(dsn, autocommit=True) as conn:
        for path in sorted(MIGRATIONS.glob("*.sql")):
            run_script(conn, path.read_text())
    yield dsn
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        admin.execute(f"drop database if exists {TEST_DB} with (force)")


@contextmanager
def as_role(conn, role: str):
    conn.execute(f"set role {role}")
    try:
        yield conn
    finally:
        conn.execute("reset role")


def rows(conn, sql: str) -> list[tuple]:
    return conn.execute(sql).fetchall()
