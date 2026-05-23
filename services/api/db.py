from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3
from typing import Any

from .config import Settings, get_settings, require_complete_settings


def connect_mysql(settings: Settings | None = None, *, with_database: bool = True) -> Any:
    import pymysql
    from pymysql.cursors import DictCursor

    resolved = settings or get_settings()
    require_complete_settings(resolved)
    kwargs: dict[str, Any] = {
        "host": resolved.mysql_host,
        "port": resolved.mysql_port,
        "user": resolved.mysql_user,
        "password": resolved.mysql_password,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    }
    if with_database:
        kwargs["database"] = resolved.mysql_database
    if resolved.mysql_ssl:
        kwargs["ssl"] = {}
    return pymysql.connect(**kwargs)


def connect(settings: Settings | None = None, *, with_database: bool = True) -> Any:
    return connect_mysql(settings, with_database=with_database)


def connect_sqlite(settings: Settings | None = None) -> sqlite3.Connection:
    resolved = settings or get_settings()
    connection = sqlite3.connect(resolved.sqlite_path)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def db_cursor(settings: Settings | None = None) -> Iterator[Any]:
    resolved = settings or get_settings()
    connection = connect_sqlite(resolved) if resolved.mode == "local" else connect_mysql(resolved)
    cursor = connection.cursor()
    try:
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def sql_placeholder(settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return "?" if resolved.mode == "local" else "%s"


def utc_now_sql(settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return "strftime('%Y-%m-%d %H:%M:%f', 'now')" if resolved.mode == "local" else "UTC_TIMESTAMP(6)"
