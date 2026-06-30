"""Dynamic catalog: departments, degree programs, and system settings."""


def get_setting(db, key: str, default: str = "") -> str:
    """Return a system setting value."""
    rows = db.execute("SELECT value FROM system_settings WHERE key = ?", key)
    return rows[0]["value"] if rows else default


def set_setting(db, key: str, value: str) -> None:
    """Upsert a system setting."""
    existing = db.execute("SELECT key FROM system_settings WHERE key = ?", key)
    if existing:
        db.execute(
            "UPDATE system_settings SET value = ?, updated_at = datetime('now') WHERE key = ?",
            str(value),
            key,
        )
    else:
        db.execute(
            "INSERT INTO system_settings (key, value) VALUES (?, ?)",
            key,
            str(value),
        )


def get_degree_credits_required(db) -> int:
    """Return credits required for degree completion."""
    try:
        return int(get_setting(db, "degree_credits_required", "120"))
    except (TypeError, ValueError):
        return 120


def get_max_credit_hours_per_semester(db) -> int:
    """Return the default maximum credit hours allowed per semester."""
    try:
        return int(get_setting(db, "max_credit_hours_per_semester", "18"))
    except (TypeError, ValueError):
        return 18


def get_programs(db, active_only: bool = True) -> list[dict]:
    """Return degree programs, optionally active only."""
    query = """
        SELECT p.*, d.code AS department_code, d.name AS department_name
        FROM programs p
        LEFT JOIN departments d ON p.department_id = d.id
    """
    if active_only:
        query += " WHERE p.is_active = 1"
    query += " ORDER BY p.name"
    return db.execute(query)


def get_program_names(db) -> list[str]:
    """Return active program names for dropdowns."""
    return [row["name"] for row in get_programs(db, active_only=True)]


def get_departments(db) -> list[dict]:
    """Return all departments ordered by name."""
    return db.execute("SELECT * FROM departments ORDER BY name")


def get_all_settings(db) -> dict[str, str]:
    """Return all system settings as a key-value dict."""
    rows = db.execute("SELECT key, value FROM system_settings ORDER BY key")
    return {row["key"]: row["value"] for row in rows}


def get_student_degree_credits(db, program: str | None) -> int:
    """Return credits required for a student's program, or the global default."""
    if program:
        rows = db.execute(
            "SELECT credits_required FROM programs WHERE name = ? AND is_active = 1",
            program,
        )
        if rows:
            return int(rows[0]["credits_required"])
    return get_degree_credits_required(db)
