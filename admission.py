"""Admission sessions (Fall / Spring) and bulk student enrollment."""

import csv
import io
import re
from typing import Any

from werkzeug.security import generate_password_hash


def format_roll_number(year: int, season: str, sequence: int) -> str:
    """Build a roll number such as 2025-F-042 for Fall or 2026-S-001 for Spring."""
    season_letter = "F" if season == "fall" else "S"
    return f"{year}-{season_letter}-{sequence:03d}"


def parse_session_token(token: str) -> tuple[str, int] | None:
    """
    Parse admission session shorthand such as Fa23 or Sp24.

    Returns (season, full_year) or None when invalid.
    """
    match = re.match(r"^(Fa|Sp)(\d{2})$", (token or "").strip(), re.IGNORECASE)
    if not match:
        return None

    season = "fall" if match.group(1).lower() == "fa" else "spring"
    year_suffix = int(match.group(2))
    year = 2000 + year_suffix
    return season, year


def normalize_department_code(code: str) -> str:
    """Normalize department codes, including common degree aliases."""
    normalized = (code or "").strip().upper()
    aliases = {
        "BSCS": "CS",
        "BSIT": "CS",
        "BBA": "BUS",
        "BENG": "ENG",
    }
    return aliases.get(normalized, normalized)


def parse_structured_login_value(value: str) -> tuple[str, str, str] | None:
    """
    Parse Fa23/BSCS/333 style login strings.

    Returns (session_token, department_code, roll_sequence) or None.
    """
    match = re.match(
        r"^(Fa|Sp)(\d{2})\s*/\s*([A-Za-z]{2,10})\s*/\s*(\d{1,4})$",
        (value or "").strip(),
        re.IGNORECASE,
    )
    if not match:
        return None

    session_token = f"{match.group(1).capitalize()}{match.group(2)}"
    if session_token.lower().startswith("sp"):
        session_token = f"Sp{match.group(2)}"
    else:
        session_token = f"Fa{match.group(2)}"

    return session_token, match.group(3).upper(), match.group(4)


def build_roll_number_from_login(session_token: str, roll_sequence: str) -> str | None:
    """Convert Fa23 + 333 into the stored roll number format (e.g. 2023-F-333)."""
    parsed = parse_session_token(session_token)
    if not parsed:
        return None

    season, year = parsed
    try:
        sequence = int((roll_sequence or "").strip())
    except (TypeError, ValueError):
        return None

    if sequence < 1 or sequence > 9999:
        return None

    return format_roll_number(year, season, sequence)


def compose_session_token(season_prefix: str, year_suffix: str) -> str | None:
    """Build Fa24 / Sp23 token from dropdown season and 2-digit year."""
    prefix = (season_prefix or "").strip().capitalize()
    year_part = (year_suffix or "").strip()

    if prefix not in ("Fa", "Sp"):
        return None
    if not re.match(r"^\d{2}$", year_part):
        return None

    return f"{prefix}{year_part}"


def split_session_token(token: str) -> tuple[str, str]:
    """Split Fa24 into (Fa, 24) for login form repopulation."""
    parsed = parse_session_token(token)
    if not parsed:
        return "", ""

    season, year = parsed
    prefix = "Fa" if season == "fall" else "Sp"
    return prefix, f"{year % 100:02d}"


LOGIN_DEGREE_LABELS = {
    "CS": "BSCS",
    "MATH": "BS Math",
    "BUS": "BBA",
    "ENG": "BEng",
    "BIO": "BS Biology",
}


def get_login_degree_options(db) -> list[dict[str, str]]:
    """Degree choices shown on the student login form."""
    rows = db.execute("SELECT code, name FROM departments ORDER BY name")
    options: list[dict[str, str]] = []
    for row in rows:
        display_code = LOGIN_DEGREE_LABELS.get(row["code"], row["code"])
        options.append(
            {
                "code": display_code,
                "label": f"{display_code} — {row['name']}",
            }
        )
    return options


def get_admission_sessions(db, open_only: bool = False) -> list[dict[str, Any]]:
    """Return admission sessions ordered by year and season."""
    query = """
        SELECT id, name, season, year, next_roll_seq, is_open,
               (SELECT COUNT(*) FROM students s WHERE s.admission_session_id = admission_sessions.id) AS student_count
        FROM admission_sessions
    """
    if open_only:
        query += " WHERE is_open = 1"
    query += " ORDER BY year DESC, CASE season WHEN 'fall' THEN 0 ELSE 1 END"
    return db.execute(query)


def get_admission_session(db, session_id: int) -> dict[str, Any] | None:
    """Return one admission session row."""
    rows = db.execute("SELECT * FROM admission_sessions WHERE id = ?", session_id)
    return rows[0] if rows else None


def create_admission_session(db, season: str, year: int) -> dict[str, Any]:
    """
    Create a Fall or Spring admission session if it does not already exist.

    Returns the session row.
    """
    season = season.lower().strip()
    if season not in ("fall", "spring"):
        raise ValueError("Season must be fall or spring.")

    year = int(year)
    name = f"{'Fall' if season == 'fall' else 'Spring'} {year}"

    existing = db.execute(
        "SELECT * FROM admission_sessions WHERE season = ? AND year = ?",
        season,
        year,
    )
    if existing:
        return existing[0]

    session_id = db.execute(
        """
        INSERT INTO admission_sessions (name, season, year, next_roll_seq, is_open)
        VALUES (?, ?, ?, 1, 1)
        """,
        name,
        season,
        year,
    )
    return get_admission_session(db, session_id)


def allocate_roll_number(db, session_id: int) -> str:
    """Reserve and return the next roll number for an admission session."""
    session_row = get_admission_session(db, session_id)
    if not session_row:
        raise ValueError("Admission session not found.")

    sequence = session_row["next_roll_seq"]
    roll_number = format_roll_number(session_row["year"], session_row["season"], sequence)
    db.execute(
        "UPDATE admission_sessions SET next_roll_seq = ? WHERE id = ?",
        sequence + 1,
        session_id,
    )
    return roll_number


def resolve_department_id(db, department_code: str | None) -> int | None:
    """Look up a department id from its code."""
    code = normalize_department_code(department_code)
    if not code:
        return None
    rows = db.execute("SELECT id FROM departments WHERE code = ?", code)
    return rows[0]["id"] if rows else None


def enroll_student_record(
    db,
    *,
    roll_number: str,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    program: str | None,
    enrollment_year: int,
    department_id: int | None,
    admission_session_id: int | None,
) -> int:
    """Insert a student user account and return the new user id."""
    password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
    user_id = db.execute(
        "INSERT INTO users (username, email, hash, role) VALUES (?, ?, ?, 'student')",
        roll_number,
        email.strip(),
        password_hash,
    )
    db.execute(
        """
        INSERT INTO students (
            user_id, student_number, first_name, last_name, department_id,
            program, enrollment_year, admission_session_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        user_id,
        roll_number,
        first_name.strip(),
        last_name.strip(),
        department_id,
        (program or "").strip() or None,
        enrollment_year,
        admission_session_id,
    )
    db.execute(
        "INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)",
        user_id,
        "Welcome to the student portal. Your account has been created by the registrar.",
        "/student/dashboard",
    )
    return user_id


def student_exists(db, roll_number: str | None = None, email: str | None = None) -> bool:
    """Return True if a roll number or email is already registered."""
    if roll_number and db.execute("SELECT id FROM students WHERE student_number = ?", roll_number):
        return True
    if roll_number and db.execute("SELECT id FROM users WHERE username = ?", roll_number):
        return True
    if email and db.execute("SELECT id FROM users WHERE email = ?", email.strip()):
        return True
    return False


def parse_students_csv(csv_text: str) -> tuple[list[dict[str, str]], list[str]]:
    """
    Parse a CSV upload into student rows.

    Expected headers: first_name, last_name, email, program, department_code
  department_code is optional.
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return [], ["CSV file is empty or missing a header row."]

    normalized_fields = {name.strip().lower(): name for name in reader.fieldnames if name}
    required = ["first_name", "last_name", "email"]
    missing = [field for field in required if field not in normalized_fields]
    if missing:
        return [], [f"Missing required column(s): {', '.join(missing)}"]

    rows: list[dict[str, str]] = []
    errors: list[str] = []

    for line_number, raw_row in enumerate(reader, start=2):
        row = {
            key: (raw_row.get(original) or "").strip()
            for key, original in normalized_fields.items()
        }
        if not any(row.values()):
            continue
        if not row.get("first_name") or not row.get("last_name") or not row.get("email"):
            errors.append(f"Line {line_number}: first_name, last_name, and email are required.")
            continue
        rows.append(row)

    if not rows and not errors:
        errors.append("No student rows found in the CSV file.")

    return rows, errors


def bulk_enroll_students(
    db,
    admission_session_id: int,
    default_password: str,
    student_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Enroll many students into one Fall or Spring admission session.

    Roll numbers are assigned automatically in order (e.g. 2025-F-001, 2025-F-002).
    """
    if len(default_password) < 8:
        raise ValueError("Default password must be at least 8 characters.")

    session_row = get_admission_session(db, admission_session_id)
    if not session_row:
        raise ValueError("Admission session not found.")
    if not session_row["is_open"]:
        raise ValueError("This admission session is closed.")

    created: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    for index, row in enumerate(student_rows, start=1):
        email = row.get("email", "").strip()
        first_name = row.get("first_name", "").strip()
        last_name = row.get("last_name", "").strip()
        program = row.get("program", "").strip() or None
        department_id = resolve_department_id(db, row.get("department_code"))

        if "@" not in email or len(email) < 5:
            failed.append(
                {
                    "row": str(index),
                    "name": f"{first_name} {last_name}".strip(),
                    "reason": "Invalid email address.",
                }
            )
            continue

        if student_exists(db, email=email):
            failed.append(
                {
                    "row": str(index),
                    "name": f"{first_name} {last_name}".strip(),
                    "email": email,
                    "reason": "Email already registered.",
                }
            )
            continue

        try:
            roll_number = allocate_roll_number(db, admission_session_id)
            enroll_student_record(
                db,
                roll_number=roll_number,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=default_password,
                program=program,
                enrollment_year=session_row["year"],
                department_id=department_id,
                admission_session_id=admission_session_id,
            )
            created.append(
                {
                    "roll_number": roll_number,
                    "name": f"{first_name} {last_name}",
                    "email": email,
                }
            )
        except Exception as exc:  # noqa: BLE001 — collect per-row failures for admin review
            failed.append(
                {
                    "row": str(index),
                    "name": f"{first_name} {last_name}".strip(),
                    "email": email,
                    "reason": str(exc),
                }
            )

    return {
        "session": session_row["name"],
        "created_count": len(created),
        "failed_count": len(failed),
        "created": created,
        "failed": failed,
    }
