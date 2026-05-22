from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from .config import Settings, get_settings, require_complete_settings


def connect(settings: Settings | None = None, *, with_database: bool = True) -> Connection:
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


@contextmanager
def db_cursor(settings: Settings | None = None) -> Iterator[DictCursor]:
    connection = connect(settings)
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
