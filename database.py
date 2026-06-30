"""
SQLite database access via SQLAlchemy 2.x.

Provides parameterized queries with ``?`` placeholders and dict-shaped rows,
matching the calling convention used throughout the application.
"""

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result


class Database:
    """
    Thin wrapper around a SQLAlchemy engine for SQLite.

    Usage::

        db = Database("sqlite:///university.db")
        rows = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        new_id = db.execute("INSERT INTO users (...) VALUES (?)", value)
    """

    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )

    def execute(self, sql: str, *args: Any) -> list[dict[str, Any]] | int:
        """
        Run a parameterized SQL statement.

        - ``SELECT`` → list of row dicts (empty list when no rows)
        - ``INSERT`` → last inserted row id
        - ``UPDATE`` / ``DELETE`` → number of affected rows
        """
        statement, params = self._bind_positional(sql.strip(), args)
        sql_upper = statement.lstrip().upper()
        is_insert = sql_upper.startswith("INSERT")

        with self.engine.begin() as connection:
            result: Result = connection.execute(text(statement), params)

            if result.returns_rows:
                return [dict(row._mapping) for row in result]

            if is_insert:
                return int(result.lastrowid or 0)

            return int(result.rowcount or 0)

    @staticmethod
    def _bind_positional(sql: str, args: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
        """Convert ``?`` placeholders to SQLAlchemy named bind parameters."""
        if not args:
            return sql, {}

        params: dict[str, Any] = {}
        parts: list[str] = []
        arg_index = 0
        in_single_quote = False
        in_double_quote = False
        i = 0

        while i < len(sql):
            char = sql[i]

            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                parts.append(char)
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                parts.append(char)
            elif char == "?" and not in_single_quote and not in_double_quote:
                key = f"p{arg_index}"
                params[key] = args[arg_index]
                parts.append(f":{key}")
                arg_index += 1
            else:
                parts.append(char)

            i += 1

        if arg_index != len(args):
            raise ValueError(
                f"SQL placeholder count ({arg_index}) does not match argument count ({len(args)})."
            )

        return "".join(parts), params
