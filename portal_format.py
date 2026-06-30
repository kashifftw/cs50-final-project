"""Format helpers for student portal display."""

import re
from datetime import datetime


def semester_short_name(name):
    """
    Convert 'Spring 2026' to 'Sp-2026' for compact dashboard labels.

    Falls back to the original name when the pattern does not match.
    """
    if not name:
        return "—"

    match = re.match(r"^(Spring|Summer|Fall|Winter)\s+(\d{4})$", name.strip(), re.I)
    if not match:
        return name

    abbrev = {"spring": "Sp", "summer": "Su", "fall": "Fa", "winter": "Wi"}
    season = abbrev.get(match.group(1).lower(), match.group(1)[:2])
    return f"{season}-{match.group(2)}"


def format_display_date(date_string):
    """Format ISO date strings as '10 Mar 2025'."""
    if not date_string:
        return "—"
    try:
        parsed = datetime.strptime(date_string[:10], "%Y-%m-%d")
        return parsed.strftime("%d %b %Y")
    except ValueError:
        return date_string


THEORY_CREDIT_HOURS = 2
LAB_COURSE_CREDIT_HOURS = 3


def credits_from_has_lab(has_lab: bool) -> int:
    """Return credit hours: 2 for theory-only, 3 when the course includes a lab."""
    return LAB_COURSE_CREDIT_HOURS if has_lab else THEORY_CREDIT_HOURS


def course_type_label(has_lab: bool) -> str:
    """Human-readable course type for enrollment display."""
    return "Theory + Lab" if has_lab else "Theory"


def course_credit_display(credits: float | int, has_lab: bool) -> str:
    """Format credits as a single subject line, e.g. '3 cr · Theory + Lab'."""
    return f"{int(credits)} cr · {course_type_label(has_lab)}"
