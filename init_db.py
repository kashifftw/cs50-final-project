"""Initialize the SQLite database from schema.sql and set password hashes."""

import json
import os

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

from portal_config import DEFAULT_PORTAL_SECTIONS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "university.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

DEFAULT_PASSWORDS = {
    "2024-F-001": "student123",
    "2024-F-002": "student123",
    "admin": "admin123",
}


def init_database() -> None:
    """Create tables, seed data, and apply real password hashes."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        sql_script = schema_file.read()

    engine = create_engine(DATABASE_URL, future=True)

    with engine.begin() as connection:
        for statement in _split_sql_script(sql_script):
            connection.execute(text(statement))

        connection.execute(
            text("INSERT INTO system_settings (key, value) VALUES ('portal_sections', :val)"),
            {"val": json.dumps(DEFAULT_PORTAL_SECTIONS)},
        )

        for username, password in DEFAULT_PASSWORDS.items():
            password_hash = generate_password_hash(
                password, method="pbkdf2:sha256", salt_length=16
            )
            connection.execute(
                text("UPDATE users SET hash = :hash WHERE username = :username"),
                {"hash": password_hash, "username": username},
            )

    print(f"Database initialized at {DB_PATH}")
    print("Demo accounts:")
    for username, password in DEFAULT_PASSWORDS.items():
        print(f"  {username} / {password}")


def _split_sql_script(script: str) -> list[str]:
    """Split a SQL file into executable statements."""
    statements: list[str] = []
    buffer: list[str] = []

    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buffer).rstrip(";").strip())
            buffer = []

    if buffer:
        statements.append("\n".join(buffer).strip())

    return [statement for statement in statements if statement]


if __name__ == "__main__":
    init_database()
