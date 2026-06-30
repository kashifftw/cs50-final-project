"""Shared helpers for session management, authorization, and validation."""

from functools import wraps

from flask import redirect, request, session, url_for


def login_required(f):
    """
    Decorator that redirects unauthenticated users to the login page.

    Preserves the originally requested URL in the query string so the user
    can be sent back after a successful login.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)

    return decorated_function


def role_required(*roles):
    """
    Restrict a route to one or more user roles.

    Usage:
        @role_required("admin")
        @role_required("student", "admin")
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("user_id") is None:
                return redirect(url_for("login", next=request.path))

            if session.get("role") not in roles:
                return redirect(url_for("dashboard"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def get_dashboard_route(role):
    """Return the primary dashboard URL for a given role."""
    routes = {
        "student": "student_dashboard",
        "admin": "admin_dashboard",
    }
    return url_for(routes.get(role, "login"))


def validate_add_student_form(data):
    """
    Validate admin student enrollment payload.

    When auto_roll is true, roll number and batch year come from the admission session.

    Returns (is_valid, error_message).
    """
    auto_roll = bool(data.get("auto_roll"))
    roll_number = (data.get("roll_number") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    enrollment_year = data.get("enrollment_year")
    admission_session_id = data.get("admission_session_id")

    if auto_roll and not admission_session_id:
        return False, "Select a Fall or Spring admission session."

    if not auto_roll and len(roll_number) < 3:
        return False, "Roll number is required."

    if "@" not in email or len(email) < 5:
        return False, "Please enter a valid email address."

    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    if not first_name or not last_name:
        return False, "First and last name are required."

    if not auto_roll and not enrollment_year:
        return False, "Batch year is required."

    if not auto_roll:
        try:
            int(enrollment_year)
        except (TypeError, ValueError):
            return False, "Batch year must be a valid year."

    return True, None
