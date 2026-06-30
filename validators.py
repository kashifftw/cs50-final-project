"""Input validation helpers for auth and profile forms."""

import re

UNIVERSITY_EMAIL_DOMAIN = "university.edu"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_university_email(email: str, domain: str | None = None) -> bool:
    """
    Return True when email uses the configured university domain.

    Args:
        email: Email address to validate.
        domain: Override domain (default university.edu).
    """
    domain = (domain or UNIVERSITY_EMAIL_DOMAIN).lower().strip()
    email = (email or "").strip().lower()
    if not EMAIL_PATTERN.match(email):
        return False
    return email.endswith(f"@{domain}")


def validate_password(password: str) -> tuple[bool, str | None]:
    """Return (ok, error_message) for password strength."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters."
    return True, None
