"""
University ERP System — Flask application entry point.

Provides authentication, role-based dashboards, and REST-style JSON endpoints
for async frontend interactions (course catalog, enrollment, grading, etc.).
"""

import os
import secrets
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from admission import (
    allocate_roll_number,
    bulk_enroll_students,
    create_admission_session,
    enroll_student_record,
    get_admission_session,
    get_admission_sessions,
    parse_students_csv,
    student_exists,
)
from database import Database
from helpers import (
    get_dashboard_route,
    login_required,
    role_required,
    validate_add_student_form,
)
from catalog import (
    get_all_settings,
    get_degree_credits_required,
    get_departments,
    get_max_credit_hours_per_semester,
    get_program_names,
    get_programs,
    get_setting,
    get_student_degree_credits,
    set_setting,
)
from portal_format import (
    course_credit_display,
    credits_from_has_lab,
    format_display_date,
    semester_short_name,
)
from portal_config import (
    enabled_sections,
    get_portal_sections,
    save_portal_sections,
    section_enabled,
)
from audit import log_audit
from portal_services import (
    get_student_attendance,
    get_student_credit_summary,
    get_student_fees as fetch_student_fees,
    get_university_email_domain,
    get_upcoming_deadlines,
    refresh_fee_statuses,
    would_exceed_credit_limit,
)
from validators import is_university_email, validate_password


load_dotenv()

# ── Application setup ──────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-unierp-secret-change-in-production")

# Development: reload templates/static without cache; enable with FLASK_DEBUG=1
_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
app.config["DEBUG"] = _debug
if _debug:
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.jinja_env.auto_reload = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "university.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "profiles")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["DATABASE"] = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

db = Database(app.config["DATABASE"])

GRADE_POINTS = {
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D": 1.0,
    "F": 0.0,
}


def authenticate_student(roll_number, password):
    """
    Look up a student by roll number and verify their password.

    Returns the matching users row, or None if credentials are invalid.
    """
    roll_number = (roll_number or "").strip()
    if not roll_number or not password:
        return None

    rows = db.execute(
        """
        SELECT u.* FROM users u
        JOIN students s ON s.user_id = u.id
        WHERE u.role = 'student' AND u.is_active = 1 AND s.is_active = 1
          AND s.student_number = ?
        """,
        roll_number,
    )
    if not rows or not check_password_hash(rows[0]["hash"], password):
        return None
    return rows[0]


def authenticate_student_credential(credential, password):
    """Authenticate a student by roll number or university email."""
    credential = (credential or "").strip()
    if not credential or not password:
        return None

    if "@" in credential:
        rows = db.execute(
            """
            SELECT u.* FROM users u
            JOIN students s ON s.user_id = u.id
            WHERE u.role = 'student' AND u.is_active = 1 AND s.is_active = 1
              AND LOWER(u.email) = LOWER(?)
            """,
            credential,
        )
    else:
        rows = db.execute(
            """
            SELECT u.* FROM users u
            JOIN students s ON s.user_id = u.id
            WHERE u.role = 'student' AND u.is_active = 1 AND s.is_active = 1
              AND s.student_number = ?
            """,
            credential,
        )

    if not rows or not check_password_hash(rows[0]["hash"], password):
        return None
    return rows[0]


def create_student_account(
    roll_number,
    first_name,
    last_name,
    email,
    password,
    program=None,
    enrollment_year=None,
    department_id=None,
    admission_session_id=None,
):
    """Create a student user account and profile record."""
    return enroll_student_record(
        db,
        roll_number=roll_number,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=password,
        program=program,
        enrollment_year=enrollment_year,
        department_id=department_id,
        admission_session_id=admission_session_id,
    )


# ── Context processors & utilities ─────────────────────────────────────────────


@app.context_processor
def inject_globals():
    """Expose unread notification count and template helpers to all pages."""
    unread = 0
    if session.get("user_id"):
        row = db.execute(
            "SELECT COUNT(*) AS count FROM notifications WHERE user_id = ? AND is_read = 0",
            session["user_id"],
        )
        unread = row[0]["count"] if row else 0
    return {
        "unread_notifications": unread,
        "semester_short_name": semester_short_name,
        "format_display_date": format_display_date,
        "portal_name": get_setting(db, "portal_name", "Campus Portal"),
        "portal_sections": enabled_sections(db),
        "student_profile": get_student_profile(session["user_id"])
        if session.get("role") == "student" and session.get("user_id")
        else None,
    }


def get_student_profile(user_id):
    """Return the student row linked to a user account."""
    rows = db.execute(
        """
        SELECT s.*, d.name AS department_name, d.code AS department_code
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE s.user_id = ?
        """,
        user_id,
    )
    return rows[0] if rows else None


def require_student_profile(*, api=False):
    """
    Return the logged-in student profile, or None after clearing a stale session.

    Used when the users row exists but the linked students row is missing.
    """
    student = get_student_profile(session.get("user_id"))
    if not student:
        session.clear()
        if not api:
            flash("Your session expired. Please sign in again.", "error")
    return student


def guard_student_section(section_key):
    """Redirect students when a portal section has been disabled by admin."""
    if not section_enabled(db, section_key):
        flash("This section is currently unavailable.", "error")
        return redirect(url_for("student_dashboard"))
    return None


@app.before_request
def validate_session_profile():
    """Clear stale sessions when the user or role profile no longer exists in the DB."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    endpoint = request.endpoint
    if endpoint in (
        "login",
        "admin_login",
        "logout",
        "index",
        "register",
        "forgot_password",
        "reset_password",
    ) or endpoint is None:
        return None

    user_rows = db.execute("SELECT id, role, is_active FROM users WHERE id = ?", user_id)
    if not user_rows or not user_rows[0]["is_active"]:
        session.clear()
        flash("Your session expired. Please sign in again.", "error")
        return redirect(url_for("login"))

    role = user_rows[0]["role"]
    session["role"] = role

    if role == "student" and not get_student_profile(user_id):
        session.clear()
        flash("Your session expired. Please sign in again.", "error")
        return redirect(url_for("login"))

    if role == "admin":
        return None

    return None


def get_active_semester():
    """Return the currently active academic semester."""
    rows = db.execute(
        "SELECT * FROM semesters WHERE is_active = 1 ORDER BY start_date DESC LIMIT 1"
    )
    return rows[0] if rows else None


def create_notification(user_id, message, link=None):
    """Insert an in-app notification for a user."""
    db.execute(
        "INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)",
        user_id,
        message,
        link,
    )


def calculate_gpa(student_id):
    """Compute cumulative GPA (CGPA) from all completed graded courses."""
    rows = db.execute(
        """
        SELECT e.grade_points, c.credits
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status = 'completed' AND e.grade_points IS NOT NULL
        """,
        student_id,
    )
    if not rows:
        return 0.0

    total_points = sum(row["grade_points"] * row["credits"] for row in rows)
    total_credits = sum(row["credits"] for row in rows)
    return round(total_points / total_credits, 2) if total_credits else 0.0


def calculate_semester_gpa(student_id, semester_id):
    """Compute semester GPA (SGPA) for one academic term."""
    rows = db.execute(
        """
        SELECT e.grade_points, c.credits
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND c.semester_id = ?
          AND e.status = 'completed' AND e.grade_points IS NOT NULL
        """,
        student_id,
        semester_id,
    )
    if not rows:
        return 0.0, 0

    total_points = sum(row["grade_points"] * row["credits"] for row in rows)
    total_credits = sum(row["credits"] for row in rows)
    sgpa = round(total_points / total_credits, 2) if total_credits else 0.0
    return sgpa, total_credits


def get_semester_academic_records(student_id):
    """Return semester-grouped academic history with per-term SGPA."""
    rows = db.execute(
        """
        SELECT s.id AS semester_id, s.name AS semester_name, s.start_date, s.is_active,
               c.code, c.title, c.credits,
               e.grade, e.grade_points, e.status
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN semesters s ON c.semester_id = s.id
        WHERE e.student_id = ? AND e.status IN ('completed', 'enrolled')
        ORDER BY s.start_date DESC, c.code
        """,
        student_id,
    )

    semesters = {}
    for row in rows:
        semester_id = row["semester_id"]
        if semester_id not in semesters:
            semesters[semester_id] = {
                "semester_id": semester_id,
                "semester_name": row["semester_name"],
                "start_date": row["start_date"],
                "is_active": row["is_active"],
                "courses": [],
            }
        semesters[semester_id]["courses"].append(
            {
                "code": row["code"],
                "title": row["title"],
                "credits": row["credits"],
                "grade": row["grade"],
                "grade_points": row["grade_points"],
                "status": row["status"],
            }
        )

    records = []
    for semester in sorted(semesters.values(), key=lambda item: item["start_date"], reverse=True):
        completed = [
            course
            for course in semester["courses"]
            if course["status"] == "completed" and course["grade_points"] is not None
        ]
        if completed:
            grade_points = sum(course["grade_points"] * course["credits"] for course in completed)
            credits_earned = sum(course["credits"] for course in completed)
            semester["sgpa"] = round(grade_points / credits_earned, 2) if credits_earned else 0.0
            semester["credits_earned"] = credits_earned
        else:
            semester["sgpa"] = None
            semester["credits_earned"] = 0

        semester["credits_attempted"] = sum(course["credits"] for course in semester["courses"])
        semester["in_progress"] = any(course["status"] == "enrolled" for course in semester["courses"])
        records.append(semester)

    return records


def get_current_enrollments(student_id, semester_id):
    """Return active enrollments for the given semester."""
    return db.execute(
        """
        SELECT e.id AS enrollment_id, e.status, e.enrolled_at,
               c.id AS course_id, c.code, c.title, c.credits,
               c.schedule_day, c.schedule_time, c.room,
               COALESCE(f.name, c.instructor_name) AS instructor_name
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        LEFT JOIN faculty f ON c.faculty_id = f.id
        WHERE e.student_id = ? AND c.semester_id = ?
          AND e.status IN ('enrolled', 'waitlisted')
        ORDER BY c.code
        """,
        student_id,
        semester_id,
    )


def get_academic_calendar(semester):
    """Build a simple academic calendar from semester metadata."""
    if not semester:
        return []

    registration = "Open" if semester["registration_open"] else "Closed"
    return [
        {"activity": "Enrollment Period", "date": registration},
        {"activity": "Semester Start", "date": format_display_date(semester["start_date"])},
        {"activity": "Semester End", "date": format_display_date(semester["end_date"])},
    ]


def count_offered_courses(semester_id):
    """Count courses offered by admin for a semester."""
    return db.execute(
        "SELECT COUNT(*) AS count FROM courses WHERE semester_id = ?",
        semester_id,
    )[0]["count"]


def student_completed_course(student_id, prerequisite_course_id):
    """
    Check whether a student has completed a prerequisite course.

    Matches the exact course or any offering sharing the same base code
    (e.g. CS50 completed in Fall satisfies CS50 prerequisite for Spring).
    """
    prereq_rows = db.execute("SELECT code FROM courses WHERE id = ?", prerequisite_course_id)
    if not prereq_rows:
        return False

    base_code = prereq_rows[0]["code"].split("-")[0]

    rows = db.execute(
        """
        SELECT e.id FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status = 'completed'
          AND (c.code = ? OR c.code LIKE ? || '-%')
        """,
        student_id,
        base_code,
        base_code,
    )
    return bool(rows)


def get_course_prerequisite_ids(course_id):
    """Return prerequisite course IDs for a catalog course."""
    rows = db.execute(
        "SELECT prerequisite_course_id FROM course_prerequisites WHERE course_id = ?",
        course_id,
    )
    return [row["prerequisite_course_id"] for row in rows]


def sync_course_prerequisites(course_id, prerequisite_ids):
    """Replace prerequisite links for a course."""
    db.execute("DELETE FROM course_prerequisites WHERE course_id = ?", course_id)
    for prereq_id in prerequisite_ids or []:
        try:
            pid = int(prereq_id)
        except (TypeError, ValueError):
            continue
        if pid == course_id:
            continue
        if db.execute("SELECT id FROM courses WHERE id = ?", pid):
            db.execute(
                "INSERT OR IGNORE INTO course_prerequisites (course_id, prerequisite_course_id) VALUES (?, ?)",
                course_id,
                pid,
            )


def course_enrollment_counts(course_id):
    """Return enrolled and waitlisted counts for capacity checks."""
    enrolled = db.execute(
        "SELECT COUNT(*) AS count FROM enrollments WHERE course_id = ? AND status = 'enrolled'",
        course_id,
    )[0]["count"]
    waitlisted = db.execute(
        "SELECT COUNT(*) AS count FROM enrollments WHERE course_id = ? AND status = 'waitlisted'",
        course_id,
    )[0]["count"]
    return enrolled, waitlisted


def resolve_has_lab_and_credits(data, existing=None):
    """
    Derive has_lab and credit hours from admin/student course payload.

    Theory-only courses are 2 credits; courses with a lab are 3 credits (single subject).
    """
    if "has_lab" in data:
        has_lab = str(data.get("has_lab")).lower() in ("1", "true", "yes", "on")
    elif existing is not None:
        has_lab = bool(existing.get("has_lab"))
    else:
        has_lab = False

    credits = credits_from_has_lab(has_lab)
    return has_lab, credits


def enrich_course_credits(row):
    """Add normalized credits and credits_label to a course or enrollment row."""
    payload = dict(row)
    has_lab = bool(payload.get("has_lab"))
    payload["has_lab"] = has_lab
    payload["credits"] = int(payload.get("credits") or credits_from_has_lab(has_lab))
    payload["credits_label"] = course_credit_display(payload["credits"], has_lab)
    return payload


def serialize_course(course_row, student_id=None):
    """Enrich a course record with enrollment stats and student-specific status."""
    enrolled, waitlisted = course_enrollment_counts(course_row["id"])
    payload = dict(course_row)
    has_lab = bool(payload.get("has_lab"))
    payload["has_lab"] = has_lab
    payload["credits"] = int(payload.get("credits") or credits_from_has_lab(has_lab))
    payload["credits_label"] = course_credit_display(payload["credits"], has_lab)
    payload["enrolled_count"] = enrolled
    payload["waitlisted_count"] = waitlisted
    payload["seats_available"] = max(course_row["capacity"] - enrolled, 0)

    if student_id:
        enrollment = db.execute(
            "SELECT status, grade FROM enrollments WHERE student_id = ? AND course_id = ?",
            student_id,
            course_row["id"],
        )
        payload["enrollment_status"] = enrollment[0]["status"] if enrollment else None
        payload["grade"] = enrollment[0]["grade"] if enrollment else None

        prereqs = db.execute(
            """
            SELECT c.id, c.code, c.title
            FROM course_prerequisites cp
            JOIN courses c ON cp.prerequisite_course_id = c.id
            WHERE cp.course_id = ?
            """,
            course_row["id"],
        )
        payload["prerequisites"] = []
        payload["prerequisites_met"] = True
        for prereq in prereqs:
            met = student_completed_course(student_id, prereq["id"])
            payload["prerequisites"].append(
                {"code": prereq["code"], "title": prereq["title"], "met": met}
            )
            if not met:
                payload["prerequisites_met"] = False

    return payload


# ── Public & auth routes ───────────────────────────────────────────────────────


@app.route("/")
def index():
    """Redirect visitors to login or their role dashboard."""
    if session.get("user_id"):
        return redirect(get_dashboard_route(session.get("role")))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a student using roll number, university email, and password."""
    form_credential = ""

    if request.method == "GET":
        if session.get("user_id"):
            return redirect(get_dashboard_route(session.get("role")))
        return render_template("login.html")

    credential = (request.form.get("roll_number") or request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    form_credential = credential

    if not credential or not password:
        flash("Roll number or email and password are required.", "error")
        return render_template("login.html", form_roll_number=form_credential)

    user = authenticate_student_credential(credential, password)
    if not user:
        flash("Invalid credentials. Check your roll number or university email.", "error")
        return render_template("login.html", form_roll_number=form_credential)
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    next_url = request.args.get("next") or request.form.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(get_dashboard_route(user["role"]))


@app.route("/login/admin", methods=["GET", "POST"])
def admin_login():
    """Authenticate an administrator using username and password."""
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(get_dashboard_route(session.get("role")))
        return render_template("admin_login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Username and password are required.", "error")
        return render_template("admin_login.html")

    rows = db.execute(
        "SELECT * FROM users WHERE username = ? AND role = 'admin' AND is_active = 1",
        username,
    )
    if not rows or not check_password_hash(rows[0]["hash"], password):
        flash("Invalid username or password.", "error")
        return render_template("admin_login.html")

    user = rows[0]
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    next_url = request.args.get("next") or request.form.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(get_dashboard_route(user["role"]))


@app.route("/login/faculty")
@app.route("/login/staff")
def legacy_admin_login_redirect():
    """Legacy faculty URLs redirect to admin login."""
    return redirect(url_for("admin_login", **request.args))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Redirect — student accounts are created by the registrar, not self-service."""
    flash(
        "Student accounts are issued by the university. Sign in with your roll number "
        "and the default password provided at enrollment.",
        "error",
    )
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Request a password reset link (demo: link shown in flash message)."""
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = (request.form.get("email") or "").strip().lower()
    domain = get_university_email_domain(db)
    if not is_university_email(email, domain):
        flash(f"Enter a valid @{domain} email address.", "error")
        return render_template("forgot_password.html")

    users = db.execute(
        "SELECT id, role FROM users WHERE LOWER(email) = ? AND is_active = 1",
        email,
    )
    if users:
        token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            users[0]["id"],
            token,
            expires,
        )
        reset_url = url_for("reset_password", token=token, _external=True)
        flash(f"Reset link (demo): {reset_url}", "success")
    else:
        flash("If an account exists for that email, a reset link has been sent.", "success")
    return redirect(url_for("login"))


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Set a new password using a valid reset token."""
    rows = db.execute(
        """
        SELECT prt.*, u.email FROM password_reset_tokens prt
        JOIN users u ON prt.user_id = u.id
        WHERE prt.token = ? AND prt.used = 0 AND prt.expires_at > datetime('now')
        """,
        token,
    )
    if not rows:
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("login"))

    reset_row = rows[0]
    if request.method == "GET":
        return render_template("reset_password.html", token=token, email=reset_row["email"])

    password = request.form.get("password") or ""
    confirm = request.form.get("confirm_password") or ""
    ok, err = validate_password(password)
    if not ok:
        flash(err, "error")
        return render_template("reset_password.html", token=token, email=reset_row["email"])
    if password != confirm:
        flash("Passwords do not match.", "error")
        return render_template("reset_password.html", token=token, email=reset_row["email"])

    db.execute(
        "UPDATE users SET hash = ? WHERE id = ?",
        generate_password_hash(password, method="pbkdf2:sha256", salt_length=16),
        reset_row["user_id"],
    )
    db.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", reset_row["id"])
    log_audit(db, "password_reset", "users", reset_row["user_id"])
    flash("Password updated. You may sign in now.", "success")
    return redirect(url_for("login"))


@app.route("/logout")
@login_required
def logout():
    """Clear the session and return to login."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Route authenticated users to their role-specific dashboard."""
    return redirect(get_dashboard_route(session.get("role")))


# ── Student routes ─────────────────────────────────────────────────────────────


@app.route("/student/dashboard")
@login_required
@role_required("student")
def student_dashboard():
    """Student home — CGPA, current enrollments, registration status, and announcements."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("dashboard")
    if blocked:
        return blocked
    semester = get_active_semester()
    semester_id = semester["id"] if semester else 0

    enrolled_count = db.execute(
        """
        SELECT COUNT(*) AS count FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status = 'enrolled' AND c.semester_id = ?
        """,
        student["id"],
        semester_id,
    )[0]["count"]

    completed_credits = db.execute(
        """
        SELECT COALESCE(SUM(c.credits), 0) AS total FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status = 'completed'
        """,
        student["id"],
    )[0]["total"]

    current_credits = db.execute(
        """
        SELECT COALESCE(SUM(c.credits), 0) AS total FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status = 'enrolled' AND c.semester_id = ?
        """,
        student["id"],
        semester_id,
    )[0]["total"]

    cgpa = calculate_gpa(student["id"])
    sgpa, _ = calculate_semester_gpa(student["id"], semester_id) if semester else (0.0, 0)
    current_enrollments = get_current_enrollments(student["id"], semester_id) if semester else []
    offered_courses = count_offered_courses(semester_id) if semester else 0
    degree_credits = get_student_degree_credits(db, student.get("program"))
    degree_progress = min(round((completed_credits / degree_credits) * 100, 1), 100) if degree_credits else 0
    academic_calendar = get_academic_calendar(semester)
    announcements = db.execute(
        """
        SELECT a.*, u.username AS author_name
        FROM announcements a
        JOIN users u ON a.author_id = u.id
        WHERE a.audience IN ('all', 'students')
        ORDER BY a.created_at DESC LIMIT 6
        """
    )

    return render_template(
        "student/dashboard.html",
        student=student,
        semester=semester,
        enrolled_count=enrolled_count,
        completed_credits=completed_credits,
        current_credits=current_credits,
        cgpa=cgpa,
        sgpa=sgpa,
        current_enrollments=current_enrollments,
        academic_calendar=academic_calendar,
        offered_courses=offered_courses,
        degree_progress=degree_progress,
        degree_credits_required=degree_credits,
        announcements=announcements,
        upcoming_deadlines=get_upcoming_deadlines(db, semester_id if semester else None),
        active_page="dashboard",
    )


@app.route("/student/courses")
@login_required
@role_required("student")
def student_courses():
    """Course registration — enroll in admin-offered courses when registration is open."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("courses")
    if blocked:
        return blocked
    semester = get_active_semester()
    departments = db.execute("SELECT id, code, name FROM departments ORDER BY name")
    semesters = db.execute(
        "SELECT id, name, is_active, registration_open FROM semesters ORDER BY start_date DESC"
    )
    return render_template(
        "student/courses.html",
        student=student,
        semester=semester,
        departments=departments,
        semesters=semesters,
        active_page="register",
    )


@app.route("/student/enrollments")
@login_required
@role_required("student")
def student_enrollments():
    """View all enrollments across semesters with drop actions."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("enrollments")
    if blocked:
        return blocked
    semesters = db.execute("SELECT id, name, is_active FROM semesters ORDER BY start_date DESC")
    return render_template(
        "student/enrollments.html",
        student=student,
        semesters=semesters,
        active_page="enrollments",
    )


@app.route("/student/schedule")
@login_required
@role_required("student")
def student_schedule():
    """Weekly timetable for the student's current enrollments."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("schedule")
    if blocked:
        return blocked
    semester = get_active_semester()

    courses = [
        enrich_course_credits(course)
        for course in db.execute(
        """
        SELECT c.*, e.status, e.grade, c.instructor_name
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status IN ('enrolled', 'waitlisted')
          AND c.semester_id = ?
        ORDER BY c.schedule_day, c.schedule_time
        """,
        student["id"],
        semester["id"] if semester else 0,
        )
    ]

    return render_template(
        "student/schedule.html",
        student=student,
        semester=semester,
        courses=courses,
        active_page="schedule",
    )


@app.route("/student/academics")
@login_required
@role_required("student")
def student_academics():
    """Semester-wise results, SGPA per term, and cumulative CGPA."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("academics")
    if blocked:
        return blocked
    cgpa = calculate_gpa(student["id"])
    semester_records = get_semester_academic_records(student["id"])

    total_credits = db.execute(
        """
        SELECT COALESCE(SUM(c.credits), 0) AS total FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status = 'completed'
        """,
        student["id"],
    )[0]["total"]

    degree_credits = get_student_degree_credits(db, student.get("program"))

    return render_template(
        "student/academics.html",
        student=student,
        cgpa=cgpa,
        semester_records=semester_records,
        total_credits=total_credits,
        degree_credits_required=degree_credits,
        active_page="academics",
    )


@app.route("/student/grades")
@login_required
@role_required("student")
def student_grades():
    """Legacy route — redirects to the academics portal."""
    return redirect(url_for("student_academics"))


@app.route("/student/profile")
@login_required
@role_required("student")
def student_profile():
    """View and update student profile and contact information."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("profile")
    if blocked:
        return blocked
    user = db.execute("SELECT username, email FROM users WHERE id = ?", session["user_id"])[0]
    cgpa = calculate_gpa(student["id"])
    return render_template(
        "student/profile.html",
        student=student,
        user=user,
        cgpa=cgpa,
        active_page="profile",
    )


@app.route("/student/attendance")
@login_required
@role_required("student")
def student_attendance():
    """View attendance percentage per enrolled course."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("attendance")
    if blocked:
        return blocked
    semester = get_active_semester()
    records = get_student_attendance(db, student["id"], semester["id"] if semester else None)
    return render_template(
        "student/attendance.html",
        student=student,
        semester=semester,
        records=records,
        active_page="attendance",
    )


@app.route("/student/fees")
@login_required
@role_required("student")
def student_fees():
    """View fee status, due dates, and payment history."""
    student = require_student_profile()
    if not student:
        return redirect(url_for("login"))
    blocked = guard_student_section("fees")
    if blocked:
        return blocked
    fee_data = fetch_student_fees(db, student["id"])
    return render_template(
        "student/fees.html",
        student=student,
        fee_data=fee_data,
        active_page="fees",
    )



# ── Admin routes ───────────────────────────────────────────────────────────────


@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    """Admin home — key stats and recent enrollment activity."""
    refresh_fee_statuses(db)
    stats = {
        "students": db.execute(
            "SELECT COUNT(*) AS count FROM students WHERE is_active = 1"
        )[0]["count"],
        "courses": db.execute("SELECT COUNT(*) AS count FROM courses")[0]["count"],
        "pending_fees": db.execute(
            """
            SELECT COUNT(*) AS count FROM student_fees
            WHERE status IN ('pending', 'partial', 'overdue') AND amount_paid < amount
            """
        )[0]["count"],
        "recent_enrollments": db.execute(
            """
            SELECT COUNT(*) AS count FROM enrollments
            WHERE status IN ('enrolled', 'waitlisted')
              AND enrolled_at >= datetime('now', '-30 days')
            """
        )[0]["count"],
    }
    recent_enrollments = db.execute(
        """
        SELECT e.status, e.enrolled_at,
               s.student_number, s.first_name, s.last_name,
               c.code, c.title, sem.name AS semester_name
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c ON e.course_id = c.id
        JOIN semesters sem ON c.semester_id = sem.id
        WHERE e.status IN ('enrolled', 'waitlisted', 'completed')
        ORDER BY e.enrolled_at DESC
        LIMIT 10
        """
    )
    semester = get_active_semester()
    portal_sections = get_portal_sections(db)
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_enrollments=recent_enrollments,
        semester=semester,
        portal_sections=portal_sections,
        active_page="dashboard",
    )


@app.route("/admin/portal")
@login_required
@role_required("admin")
def admin_portal():
    """Configure which student portal sections are visible."""
    return render_template(
        "admin/portal.html",
        portal_sections=get_portal_sections(db),
        active_page="portal",
    )


@app.route("/admin/manage")
@login_required
@role_required("admin")
def admin_manage():
    """Registrar console — semesters, courses, departments, programs, and settings."""
    stats = {
        "students": db.execute("SELECT COUNT(*) AS count FROM students")[0]["count"],
        "courses": db.execute("SELECT COUNT(*) AS count FROM courses")[0]["count"],
        "enrollments": db.execute(
            "SELECT COUNT(*) AS count FROM enrollments WHERE status = 'enrolled'"
        )[0]["count"],
    }
    semester = get_active_semester()
    departments = db.execute("SELECT id, code, name FROM departments ORDER BY name")
    semesters = db.execute("SELECT * FROM semesters ORDER BY start_date DESC")

    return render_template(
        "admin/manage.html",
        stats=stats,
        semester=semester,
        departments=departments,
        semesters=semesters,
        active_page="manage",
    )


@app.route("/admin/students")
@login_required
@role_required("admin")
def admin_students():
    """Student enrollment — single add, bulk CSV import, admission sessions."""
    users = db.execute(
        """
        SELECT u.id, u.username, u.email, u.role, u.created_at,
               s.id AS student_id, s.student_number, s.first_name || ' ' || s.last_name AS student_name,
               s.first_name, s.last_name, s.program, s.enrollment_year, s.department_id,
               s.max_credit_hours,
               a.name AS admission_session, a.id AS admission_session_id
        FROM users u
        LEFT JOIN students s ON u.id = s.user_id
        LEFT JOIN admission_sessions a ON s.admission_session_id = a.id
        WHERE u.role = 'student'
        ORDER BY u.username
        """
    )
    departments = get_departments(db)
    admission_sessions = get_admission_sessions(db)
    return render_template(
        "admin/students.html",
        users=users,
        departments=departments,
        degree_options=get_program_names(db),
        admission_sessions=admission_sessions,
        active_page="students",
    )


@app.route("/admin/enrollments")
@login_required
@role_required("admin")
def admin_enrollments():
    """Manage enrollments and post grades per course."""
    semester = get_active_semester()
    courses = db.execute(
        """
        SELECT c.*, s.name AS semester_name,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id AND e.status = 'enrolled') AS enrolled_count
        FROM courses c
        JOIN semesters s ON c.semester_id = s.id
        WHERE c.semester_id = ?
        ORDER BY c.code
        """,
        semester["id"] if semester else 0,
    )
    semesters = db.execute("SELECT id, name FROM semesters ORDER BY start_date DESC")
    students = db.execute(
        "SELECT id, student_number, first_name, last_name FROM students WHERE is_active = 1 ORDER BY student_number"
    )
    return render_template(
        "admin/enrollments.html",
        semester=semester,
        courses=courses,
        students=students,
        grade_letters=list(GRADE_POINTS.keys()),
        active_page="enrollments",
    )


@app.route("/admin/announcements")
@login_required
@role_required("admin")
def admin_announcements():
    """Publish and review university announcements."""
    announcements = db.execute(
        """
        SELECT a.*, u.username AS author_name
        FROM announcements a
        JOIN users u ON a.author_id = u.id
        ORDER BY a.created_at DESC
        """
    )
    return render_template(
        "admin/announcements.html",
        announcements=announcements,
        active_page="announcements",
    )


@app.route("/admin/attendance")
@login_required
@role_required("admin")
def admin_attendance():
    """Record and manage student attendance by course."""
    semester = get_active_semester()
    courses = db.execute(
        """
        SELECT c.id, c.code, c.title, s.name AS semester_name,
               COALESCE(f.name, c.instructor_name) AS instructor_name
        FROM courses c
        JOIN semesters s ON c.semester_id = s.id
        LEFT JOIN faculty f ON c.faculty_id = f.id
        WHERE c.semester_id = ?
        ORDER BY c.code
        """,
        semester["id"] if semester else 0,
    )
    return render_template(
        "admin/attendance.html",
        semester=semester,
        courses=courses,
        active_page="attendance",
    )


@app.route("/admin/fees")
@login_required
@role_required("admin")
def admin_fees():
    """Manage fee structure, student charges, and payments."""
    refresh_fee_statuses(db)
    fee_items = db.execute(
        """
        SELECT fi.*, s.name AS semester_name
        FROM fee_items fi
        LEFT JOIN semesters s ON fi.semester_id = s.id
        ORDER BY fi.id DESC
        """
    )
    overdue_students = db.execute(
        """
        SELECT DISTINCT st.id, st.student_number, st.first_name, st.last_name,
               COUNT(sf.id) AS overdue_count,
               SUM(sf.amount - sf.amount_paid) AS total_overdue
        FROM students st
        JOIN student_fees sf ON sf.student_id = st.id
        WHERE sf.status = 'overdue'
        GROUP BY st.id
        ORDER BY total_overdue DESC
        """
    )
    semesters = db.execute("SELECT id, name FROM semesters ORDER BY start_date DESC")
    students = db.execute(
        "SELECT id, student_number, first_name, last_name FROM students WHERE is_active = 1 ORDER BY student_number"
    )
    return render_template(
        "admin/fees.html",
        fee_items=fee_items,
        overdue_students=overdue_students,
        semesters=semesters,
        students=students,
        active_page="fees",
    )


@app.route("/faculty/<path:legacy>")
def faculty_legacy_redirect(legacy):
    """Legacy faculty URLs redirect to the admin console."""
    mapping = {
        "manage": "admin_manage",
        "students": "admin_students",
        "announcements": "admin_announcements",
        "dashboard": "admin_dashboard",
    }
    first = legacy.split("/")[0]
    return redirect(url_for(mapping.get(first, "admin_dashboard")))


@app.route("/admin/users")
def admin_users_redirect():
    return redirect(url_for("admin_students"))


@app.route("/admin/announcements-legacy")
def admin_announcements_redirect():
    return redirect(url_for("admin_announcements"))


# ── JSON API — shared ──────────────────────────────────────────────────────────


@app.route("/api/departments")
@login_required
def api_departments():
    """List all academic departments."""
    departments = db.execute("SELECT id, code, name FROM departments ORDER BY name")
    return jsonify(departments)


@app.route("/api/semesters")
@login_required
def api_semesters():
    """List all semesters."""
    semesters = db.execute("SELECT * FROM semesters ORDER BY start_date DESC")
    return jsonify(semesters)


@app.route("/api/notifications")
@login_required
def api_notifications():
    """Return the current user's notifications."""
    notifications = db.execute(
        """
        SELECT id, message, link, is_read, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 20
        """,
        session["user_id"],
    )
    return jsonify(notifications)


@app.route("/api/notifications/read", methods=["POST"])
@login_required
def api_notifications_read():
    """Mark one or all notifications as read."""
    data = request.get_json(silent=True) or {}
    notification_id = data.get("notification_id")

    if notification_id:
        db.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            notification_id,
            session["user_id"],
        )
    else:
        db.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
            session["user_id"],
        )

    return jsonify({"success": True})


@app.route("/api/announcements")
@login_required
def api_announcements():
    """Return announcements filtered by the user's role."""
    role = session.get("role", "student")

    if role == "student":
        announcements = db.execute(
            """
            SELECT a.id, a.title, a.content, a.audience, a.created_at, u.username AS author_name
            FROM announcements a
            JOIN users u ON a.author_id = u.id
            WHERE a.audience IN ('all', 'students')
            ORDER BY a.created_at DESC
            """
        )
    elif role == "admin":
        announcements = db.execute(
            """
            SELECT a.id, a.title, a.content, a.audience, a.created_at, u.username AS author_name
            FROM announcements a
            JOIN users u ON a.author_id = u.id
            ORDER BY a.created_at DESC
            """
        )
    else:
        announcements = db.execute(
            """
            SELECT a.id, a.title, a.content, a.audience, a.created_at, u.username AS author_name
            FROM announcements a
            JOIN users u ON a.author_id = u.id
            ORDER BY a.created_at DESC
            """
        )

    return jsonify(announcements)


# ── JSON API — student ─────────────────────────────────────────────────────────


@app.route("/api/courses")
@login_required
@role_required("student")
def api_courses():
    """
    Search and filter the course catalog.

    Query params: q, department_id, semester_id
    """
    student = require_student_profile(api=True)
    if not student:
        return jsonify({"success": False, "message": "Session expired. Please sign in again."}), 401
    search = (request.args.get("q") or "").strip()
    department_id = request.args.get("department_id")
    semester_id = request.args.get("semester_id")

    if not semester_id:
        active = get_active_semester()
        semester_id = active["id"] if active else None

    query = """
        SELECT c.*, d.code AS department_code, d.name AS department_name,
               c.instructor_name,
               s.name AS semester_name, s.registration_open
        FROM courses c
        JOIN departments d ON c.department_id = d.id
        JOIN semesters s ON c.semester_id = s.id
        WHERE c.semester_id = ?
    """
    params = [semester_id]

    if department_id:
        query += " AND c.department_id = ?"
        params.append(department_id)

    if search:
        query += " AND (c.code LIKE ? OR c.title LIKE ? OR c.description LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    query += " ORDER BY c.code"
    courses = db.execute(query, *params)
    return jsonify([serialize_course(c, student["id"]) for c in courses])


@app.route("/api/enroll", methods=["POST"])
@login_required
@role_required("student")
def api_enroll():
    """Enroll or waitlist a student in a course with prerequisite validation."""
    student = require_student_profile(api=True)
    if not student:
        return jsonify({"success": False, "message": "Session expired. Please sign in again."}), 401
    data = request.get_json(silent=True) or {}
    course_id = data.get("course_id")

    if not course_id:
        return jsonify({"success": False, "message": "Course ID is required."}), 400

    course_rows = db.execute(
        """
        SELECT c.*, s.registration_open, s.name AS semester_name
        FROM courses c
        JOIN semesters s ON c.semester_id = s.id
        WHERE c.id = ?
        """,
        course_id,
    )
    if not course_rows:
        return jsonify({"success": False, "message": "Course not found."}), 404

    course = course_rows[0]
    if not course["registration_open"]:
        return jsonify({"success": False, "message": "Registration is closed for this semester."}), 403

    existing = db.execute(
        "SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?",
        student["id"],
        course_id,
    )
    if existing and existing[0]["status"] in ("enrolled", "waitlisted"):
        return jsonify({"success": False, "message": "You are already registered for this course."}), 409

    prereqs = db.execute(
        "SELECT prerequisite_course_id FROM course_prerequisites WHERE course_id = ?",
        course_id,
    )
    for prereq in prereqs:
        if not student_completed_course(student["id"], prereq["prerequisite_course_id"]):
            return jsonify(
                {"success": False, "message": "Prerequisites not met for this course."}
            ), 403

    enrolled_count, _ = course_enrollment_counts(course_id)
    status = "enrolled" if enrolled_count < course["capacity"] else "waitlisted"

    if status == "enrolled":
        exceeds, credit_msg, _ = would_exceed_credit_limit(
            db, student, course["semester_id"], course["credits"]
        )
        if exceeds:
            return jsonify({"success": False, "message": credit_msg}), 403

    if existing:
        db.execute(
            "UPDATE enrollments SET status = ?, enrolled_at = datetime('now'), grade = NULL, grade_points = NULL WHERE id = ?",
            status,
            existing[0]["id"],
        )
    else:
        db.execute(
            "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, ?)",
            student["id"],
            course_id,
            status,
        )

    message = (
        f"Successfully enrolled in {course['code']}."
        if status == "enrolled"
        else f"Added to waitlist for {course['code']} — course is at capacity."
    )
    create_notification(
        session["user_id"],
        message,
        url_for("student_schedule"),
    )
    log_audit(db, "enroll", "enrollments", course_id, {"student_id": student["id"], "status": status})

    return jsonify({"success": True, "message": message, "status": status})


@app.route("/api/drop", methods=["POST"])
@login_required
@role_required("student")
def api_drop():
    """Drop an enrollment (or leave waitlist)."""
    student = require_student_profile(api=True)
    if not student:
        return jsonify({"success": False, "message": "Session expired. Please sign in again."}), 401
    data = request.get_json(silent=True) or {}
    course_id = data.get("course_id")

    if not course_id:
        return jsonify({"success": False, "message": "Course ID is required."}), 400

    enrollment = db.execute(
        "SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ? AND status IN ('enrolled', 'waitlisted')",
        student["id"],
        course_id,
    )
    if not enrollment:
        return jsonify({"success": False, "message": "No active enrollment found."}), 404

    db.execute(
        "UPDATE enrollments SET status = 'dropped' WHERE id = ?",
        enrollment[0]["id"],
    )

    # Promote first waitlisted student if a seat opens
    if enrollment[0]["status"] == "enrolled":
        waitlisted = db.execute(
            """
            SELECT e.id, e.student_id, s.user_id
            FROM enrollments e
            JOIN students s ON e.student_id = s.id
            WHERE e.course_id = ? AND e.status = 'waitlisted'
            ORDER BY e.enrolled_at ASC LIMIT 1
            """,
            course_id,
        )
        if waitlisted:
            db.execute(
                "UPDATE enrollments SET status = 'enrolled' WHERE id = ?",
                waitlisted[0]["id"],
            )
            course = db.execute("SELECT code FROM courses WHERE id = ?", course_id)[0]
            create_notification(
                waitlisted[0]["user_id"],
                f"You have been moved from waitlist to enrolled in {course['code']}.",
                url_for("student_schedule"),
            )

    course = db.execute("SELECT code FROM courses WHERE id = ?", course_id)[0]
    create_notification(
        session["user_id"],
        f"You dropped {course['code']}.",
        url_for("student_courses"),
    )
    log_audit(db, "drop", "enrollments", enrollment[0]["id"], {"student_id": student["id"], "course_id": course_id})

    return jsonify({"success": True, "message": f"Dropped {course['code']} successfully."})


@app.route("/api/student/enrollments")
@login_required
@role_required("student")
def api_student_enrollments():
    """Return the student's enrollments, optionally filtered by semester."""
    student = require_student_profile(api=True)
    if not student:
        return jsonify({"success": False, "message": "Session expired. Please sign in again."}), 401
    semester_id = request.args.get("semester_id")

    query = """
        SELECT e.id AS enrollment_id, e.status, e.grade, e.grade_points, e.enrolled_at,
               c.id AS course_id, c.code, c.title, c.credits, c.has_lab,
               c.schedule_day, c.schedule_time, c.room,
               s.id AS semester_id, s.name AS semester_name, s.registration_open, s.is_active,
               c.instructor_name
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN semesters s ON c.semester_id = s.id
        WHERE e.student_id = ? AND e.status != 'dropped'
    """
    params = [student["id"]]

    if semester_id:
        query += " AND c.semester_id = ?"
        params.append(semester_id)

    query += " ORDER BY s.start_date DESC, c.code"
    rows = db.execute(query, *params)
    return jsonify([enrich_course_credits(row) for row in rows])


@app.route("/api/student/academics")
@login_required
@role_required("student")
def api_student_academics():
    """Return CGPA, degree progress, and semester-wise SGPA breakdown."""
    student = require_student_profile(api=True)
    if not student:
        return jsonify({"success": False, "message": "Session expired. Please sign in again."}), 401
    cgpa = calculate_gpa(student["id"])
    semester_records = get_semester_academic_records(student["id"])

    completed_credits = db.execute(
        """
        SELECT COALESCE(SUM(c.credits), 0) AS total FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND e.status = 'completed'
        """,
        student["id"],
    )[0]["total"]

    degree_credits = get_student_degree_credits(db, student.get("program"))

    return jsonify(
        {
            "cgpa": cgpa,
            "completed_credits": completed_credits,
            "degree_credits_required": degree_credits,
            "degree_progress": min(
                round((completed_credits / degree_credits) * 100, 1), 100
            ) if degree_credits else 0,
            "semesters": semester_records,
        }
    )


@app.route("/api/student/credit-hours")
@login_required
@role_required("student")
def api_student_credit_hours():
    """Return enrolled credit hours vs the student's semester limit."""
    student = require_student_profile(api=True)
    if not student:
        return jsonify({"success": False, "message": "Session expired."}), 401

    semester_id = request.args.get("semester_id", type=int)
    if not semester_id:
        semester = get_active_semester()
        semester_id = semester["id"] if semester else None

    if not semester_id:
        return jsonify({"success": False, "message": "No semester selected."}), 400

    return jsonify(get_student_credit_summary(db, student, semester_id))


@app.route("/api/student/registration-status")
@login_required
@role_required("student")
def api_student_registration_status():
    """Return whether course registration is open and how many courses are offered."""
    semester = get_active_semester()
    if not semester:
        return jsonify({"open": False, "message": "No active semester configured."})

    offered = count_offered_courses(semester["id"])
    student = require_student_profile(api=True)
    credit_summary = (
        get_student_credit_summary(db, student, semester["id"]) if student else None
    )
    return jsonify(
        {
            "semester_id": semester["id"],
            "semester_name": semester["name"],
            "open": bool(semester["registration_open"]),
            "offered_courses": offered,
            "credit_hours": credit_summary,
            "message": (
                f"{offered} courses available — registration is open."
                if semester["registration_open"]
                else "Registration is closed for this semester."
            ),
        }
    )


# ── JSON API — admin enrollments & grades ───────────────────────────────────────


@app.route("/api/admin/roster/<int:course_id>")
@login_required
@role_required("admin")
def api_admin_roster(course_id):
    """Return enrolled students for a course."""
    course = db.execute("SELECT * FROM courses WHERE id = ?", course_id)
    if not course:
        return jsonify({"success": False, "message": "Course not found."}), 404

    roster = db.execute(
        """
        SELECT e.id AS enrollment_id, s.student_number, s.first_name, s.last_name,
               e.status, e.grade, e.grade_points, e.enrolled_at
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        WHERE e.course_id = ? AND e.status IN ('enrolled', 'waitlisted', 'completed')
        ORDER BY s.last_name, s.first_name
        """,
        course_id,
    )
    return jsonify({"course": course[0], "roster": roster})


@app.route("/api/admin/grades", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_grades():
    """Submit or update a letter grade for a student enrollment."""
    data = request.get_json(silent=True) or {}
    enrollment_id = data.get("enrollment_id")
    grade = (data.get("grade") or "").strip().upper()

    if grade not in GRADE_POINTS:
        return jsonify({"success": False, "message": "Invalid grade letter."}), 400

    enrollment = db.execute(
        """
        SELECT e.*, c.code, s.user_id AS student_user_id
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN students s ON e.student_id = s.id
        WHERE e.id = ?
        """,
        enrollment_id,
    )
    if not enrollment:
        return jsonify({"success": False, "message": "Enrollment not found."}), 404

    grade_points = GRADE_POINTS[grade]
    db.execute(
        "UPDATE enrollments SET grade = ?, grade_points = ?, status = 'completed' WHERE id = ?",
        grade,
        grade_points,
        enrollment_id,
    )

    row = enrollment[0]
    create_notification(
        row["student_user_id"],
        f"Grade posted: {row['code']} — {grade}",
        url_for("student_academics"),
    )
    log_audit(db, "grade_update", "enrollments", enrollment_id, {"grade": grade, "course": row["code"]})

    return jsonify({"success": True, "message": f"Grade {grade} recorded.", "grade_points": grade_points})


# ── JSON API — admin ───────────────────────────────────────────────────────────


@app.route("/api/admin/courses", methods=["GET", "POST"])
@login_required
@role_required("admin")
def api_admin_courses():
    """List or create courses."""
    if request.method == "GET":
        semester_id = request.args.get("semester_id")
        query = """
            SELECT c.*, d.code AS department_code, s.name AS semester_name,
                   COALESCE(f.name, c.instructor_name) AS instructor_name, f.id AS faculty_id
            FROM courses c
            JOIN departments d ON c.department_id = d.id
            JOIN semesters s ON c.semester_id = s.id
            LEFT JOIN faculty f ON c.faculty_id = f.id
        """
        if semester_id:
            courses = db.execute(query + " WHERE c.semester_id = ? ORDER BY c.code", semester_id)
        else:
            courses = db.execute(query + " ORDER BY s.start_date DESC, c.code")
        payload = []
        for course in courses:
            row = dict(course)
            row["prerequisite_ids"] = get_course_prerequisite_ids(course["id"])
            payload.append(row)
        return jsonify(payload)

    data = request.get_json(silent=True) or {}
    required = ["code", "title", "department_id", "semester_id", "capacity"]
    for field in required:
        if not data.get(field):
            return jsonify({"success": False, "message": f"Missing field: {field}"}), 400

    has_lab, credits = resolve_has_lab_and_credits(data)
    faculty_id = data.get("faculty_id")
    instructor_name = (data.get("instructor_name") or "").strip() or None
    if faculty_id:
        fac = db.execute("SELECT name FROM faculty WHERE id = ?", faculty_id)
        if fac:
            instructor_name = fac[0]["name"]

    course_id = db.execute(
        """
        INSERT INTO courses (code, title, description, credits, has_lab, department_id, faculty_id,
                             instructor_name, semester_id, capacity, schedule_day, schedule_time, room)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        data["code"].strip().upper(),
        data["title"].strip(),
        (data.get("description") or "").strip(),
        credits,
        1 if has_lab else 0,
        data["department_id"],
        faculty_id,
        instructor_name,
        data["semester_id"],
        int(data["capacity"]),
        (data.get("schedule_day") or "").strip(),
        (data.get("schedule_time") or "").strip(),
        (data.get("room") or "").strip(),
    )
    sync_course_prerequisites(course_id, data.get("prerequisite_ids"))
    log_audit(db, "course_create", "courses", course_id, {"code": data["code"], "credits": credits})
    return jsonify({"success": True, "message": "Course created successfully."})


@app.route("/api/admin/courses/<int:course_id>", methods=["PUT", "DELETE"])
@login_required
@role_required("admin")
def api_admin_course_detail(course_id):
    """Update or remove a course from the catalog."""
    existing = db.execute("SELECT * FROM courses WHERE id = ?", course_id)
    if not existing:
        return jsonify({"success": False, "message": "Course not found."}), 404

    if request.method == "DELETE":
        db.execute("DELETE FROM courses WHERE id = ?", course_id)
        return jsonify({"success": True, "message": "Course deleted."})

    data = request.get_json(silent=True) or {}
    required = ["code", "title", "department_id", "semester_id", "capacity"]
    for field in required:
        if not data.get(field):
            return jsonify({"success": False, "message": f"Missing field: {field}"}), 400

    has_lab, credits = resolve_has_lab_and_credits(data, existing[0])
    faculty_id = data.get("faculty_id")
    instructor_name = (data.get("instructor_name") or "").strip() or None
    if faculty_id:
        fac = db.execute("SELECT name FROM faculty WHERE id = ?", faculty_id)
        if fac:
            instructor_name = fac[0]["name"]

    db.execute(
        """
        UPDATE courses
        SET code = ?, title = ?, description = ?, credits = ?, has_lab = ?, department_id = ?,
            faculty_id = ?, instructor_name = ?, semester_id = ?, capacity = ?,
            schedule_day = ?, schedule_time = ?, room = ?
        WHERE id = ?
        """,
        data["code"].strip().upper(),
        data["title"].strip(),
        (data.get("description") or "").strip(),
        credits,
        1 if has_lab else 0,
        data["department_id"],
        faculty_id,
        instructor_name,
        data["semester_id"],
        int(data["capacity"]),
        (data.get("schedule_day") or "").strip(),
        (data.get("schedule_time") or "").strip(),
        (data.get("room") or "").strip(),
        course_id,
    )
    sync_course_prerequisites(course_id, data.get("prerequisite_ids"))
    log_audit(db, "course_update", "courses", course_id)
    return jsonify({"success": True, "message": "Course updated."})


@app.route("/api/admin/semesters", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_semesters():
    """Create a semester or toggle active / registration flags."""
    data = request.get_json(silent=True) or {}
    action = data.get("action", "create")

    if action == "toggle_active":
        semester_id = data.get("semester_id")
        db.execute("UPDATE semesters SET is_active = 0")
        db.execute("UPDATE semesters SET is_active = 1 WHERE id = ?", semester_id)
        return jsonify({"success": True, "message": "Active semester updated."})

    if action == "toggle_registration":
        semester_id = data.get("semester_id")
        current = db.execute("SELECT registration_open FROM semesters WHERE id = ?", semester_id)
        if not current:
            return jsonify({"success": False, "message": "Semester not found."}), 404
        new_value = 0 if current[0]["registration_open"] else 1
        db.execute("UPDATE semesters SET registration_open = ? WHERE id = ?", new_value, semester_id)
        status = "opened" if new_value else "closed"
        return jsonify({"success": True, "message": f"Registration {status}."})

    if action == "update":
        semester_id = data.get("semester_id")
        name = (data.get("name") or "").strip()
        start_date = (data.get("start_date") or "").strip()
        end_date = (data.get("end_date") or "").strip()
        if not semester_id or not name or not start_date or not end_date:
            return jsonify({"success": False, "message": "Semester id, name, and dates are required."}), 400
        db.execute(
            "UPDATE semesters SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
            name,
            start_date,
            end_date,
            semester_id,
        )
        return jsonify({"success": True, "message": "Semester updated."})

    if action == "delete":
        semester_id = data.get("semester_id")
        linked = db.execute("SELECT COUNT(*) AS count FROM courses WHERE semester_id = ?", semester_id)[0]["count"]
        if linked:
            return jsonify({"success": False, "message": "Remove courses from this semester first."}), 400
        db.execute("DELETE FROM semesters WHERE id = ?", semester_id)
        return jsonify({"success": True, "message": "Semester deleted."})

    name = (data.get("name") or "").strip()
    start_date = (data.get("start_date") or "").strip()
    end_date = (data.get("end_date") or "").strip()
    if not name or not start_date or not end_date:
        return jsonify({"success": False, "message": "Name and dates are required."}), 400

    db.execute(
        "INSERT INTO semesters (name, start_date, end_date) VALUES (?, ?, ?)",
        name,
        start_date,
        end_date,
    )
    return jsonify({"success": True, "message": "Semester created."})


@app.route("/api/admin/announcements", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_announcements_create():
    """Publish a university-wide announcement."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    audience = data.get("audience", "all")

    if audience not in ("all", "students"):
        return jsonify({"success": False, "message": "Invalid audience."}), 400

    if not title or not content:
        return jsonify({"success": False, "message": "Title and content are required."}), 400

    db.execute(
        "INSERT INTO announcements (title, content, author_id, audience) VALUES (?, ?, ?, ?)",
        title,
        content,
        session["user_id"],
        audience,
    )
    return jsonify({"success": True, "message": "Announcement published."})


@app.route("/api/admin/announcements/<int:announcement_id>", methods=["PUT", "DELETE"])
@login_required
@role_required("admin")
def api_admin_announcement_detail(announcement_id):
    """Update or remove a university announcement."""
    existing = db.execute("SELECT id FROM announcements WHERE id = ?", announcement_id)
    if not existing:
        return jsonify({"success": False, "message": "Announcement not found."}), 404

    if request.method == "DELETE":
        db.execute("DELETE FROM announcements WHERE id = ?", announcement_id)
        return jsonify({"success": True, "message": "Announcement deleted."})

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    audience = data.get("audience", "all")

    if audience not in ("all", "students"):
        return jsonify({"success": False, "message": "Invalid audience."}), 400
    if not title or not content:
        return jsonify({"success": False, "message": "Title and content are required."}), 400

    db.execute(
        "UPDATE announcements SET title = ?, content = ?, audience = ? WHERE id = ?",
        title,
        content,
        audience,
        announcement_id,
    )
    return jsonify({"success": True, "message": "Announcement updated."})


@app.route("/api/admin/departments", methods=["GET", "POST"])
@login_required
@role_required("admin")
def api_admin_departments():
    """List or create academic departments."""
    if request.method == "GET":
        return jsonify(get_departments(db))

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"success": False, "message": "Code and name are required."}), 400

    try:
        db.execute("INSERT INTO departments (code, name) VALUES (?, ?)", code, name)
    except Exception:
        return jsonify({"success": False, "message": "Department code already exists."}), 409

    return jsonify({"success": True, "message": f"Department {code} created."})


@app.route("/api/admin/departments/<int:department_id>", methods=["PUT", "DELETE"])
@login_required
@role_required("admin")
def api_admin_department_detail(department_id):
    """Update or remove a department."""
    existing = db.execute("SELECT id FROM departments WHERE id = ?", department_id)
    if not existing:
        return jsonify({"success": False, "message": "Department not found."}), 404

    if request.method == "DELETE":
        linked = db.execute(
            "SELECT COUNT(*) AS count FROM courses WHERE department_id = ?", department_id
        )[0]["count"]
        if linked:
            return jsonify({"success": False, "message": "Remove courses in this department first."}), 400
        db.execute("DELETE FROM departments WHERE id = ?", department_id)
        return jsonify({"success": True, "message": "Department deleted."})

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"success": False, "message": "Code and name are required."}), 400

    db.execute(
        "UPDATE departments SET code = ?, name = ? WHERE id = ?",
        code,
        name,
        department_id,
    )
    return jsonify({"success": True, "message": "Department updated."})


@app.route("/api/admin/programs", methods=["GET", "POST"])
@login_required
@role_required("admin")
def api_admin_programs():
    """List or create degree programs."""
    if request.method == "GET":
        active_only = request.args.get("active_only", "0") != "0"
        return jsonify(get_programs(db, active_only=active_only))

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Program name is required."}), 400

    credits = int(data.get("credits_required") or 120)
    department_id = data.get("department_id") or None

    try:
        db.execute(
            "INSERT INTO programs (name, department_id, credits_required) VALUES (?, ?, ?)",
            name,
            department_id,
            credits,
        )
    except Exception:
        return jsonify({"success": False, "message": "Program name already exists."}), 409

    return jsonify({"success": True, "message": f"Program {name} created."})


@app.route("/api/admin/programs/<int:program_id>", methods=["PUT", "DELETE"])
@login_required
@role_required("admin")
def api_admin_program_detail(program_id):
    """Update or deactivate a degree program."""
    existing = db.execute("SELECT id FROM programs WHERE id = ?", program_id)
    if not existing:
        return jsonify({"success": False, "message": "Program not found."}), 404

    if request.method == "DELETE":
        db.execute("UPDATE programs SET is_active = 0 WHERE id = ?", program_id)
        return jsonify({"success": True, "message": "Program deactivated."})

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Program name is required."}), 400

    credits = int(data.get("credits_required") or 120)
    department_id = data.get("department_id") or None
    is_active = 1 if data.get("is_active", True) else 0

    db.execute(
        """
        UPDATE programs
        SET name = ?, department_id = ?, credits_required = ?, is_active = ?
        WHERE id = ?
        """,
        name,
        department_id,
        credits,
        is_active,
        program_id,
    )
    return jsonify({"success": True, "message": "Program updated."})


@app.route("/api/admin/settings", methods=["GET", "PUT"])
@login_required
@role_required("admin")
def api_admin_settings():
    """Read or update portal-wide settings."""
    if request.method == "GET":
        return jsonify(get_all_settings(db))

    data = request.get_json(silent=True) or {}
    allowed = ("degree_credits_required", "portal_name", "registration_message", "max_credit_hours_per_semester")
    updated = 0
    for key in allowed:
        if key in data:
            set_setting(db, key, str(data[key]).strip())
            updated += 1

    if not updated:
        return jsonify({"success": False, "message": "No valid settings provided."}), 400

    return jsonify({"success": True, "message": "Settings saved."})


@app.route("/api/admin/portal-sections", methods=["GET", "PUT"])
@login_required
@role_required("admin")
def api_admin_portal_sections():
    """Read or update student portal section visibility."""
    if request.method == "GET":
        return jsonify(get_portal_sections(db))

    data = request.get_json(silent=True) or {}
    sections = data.get("sections")
    if not isinstance(sections, dict):
        return jsonify({"success": False, "message": "Invalid sections payload."}), 400

    save_portal_sections(db, sections)
    return jsonify({"success": True, "message": "Portal sections updated."})


@app.route("/api/admin/students", methods=["GET"])
@login_required
@role_required("admin")
def api_admin_students_list():
    """Return all student records for editing."""
    students = db.execute(
        """
        SELECT s.id, s.user_id, s.student_number, s.first_name, s.last_name,
               s.program, s.enrollment_year, s.department_id, s.admission_session_id,
               s.max_credit_hours, u.email
        FROM students s
        JOIN users u ON s.user_id = u.id
        ORDER BY s.student_number
        """
    )
    return jsonify(students)


@app.route("/api/admin/students/<int:student_id>", methods=["PUT", "DELETE"])
@login_required
@role_required("admin")
def api_admin_student_detail(student_id):
    """Update or remove a student account."""
    rows = db.execute(
        """
        SELECT s.*, u.email FROM students s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
        """,
        student_id,
    )
    if not rows:
        return jsonify({"success": False, "message": "Student not found."}), 404

    student = rows[0]

    if request.method == "DELETE":
        db.execute("UPDATE users SET is_active = 0 WHERE id = ?", student["user_id"])
        db.execute("UPDATE students SET is_active = 0 WHERE id = ?", student_id)
        log_audit(db, "student_deactivate", "students", student_id)
        return jsonify({"success": True, "message": "Student deactivated."})

    data = request.get_json(silent=True) or {}
    roll_number = (data.get("roll_number") or student["student_number"]).strip()
    email = (data.get("email") or student["email"]).strip()
    first_name = (data.get("first_name") or student["first_name"]).strip()
    last_name = (data.get("last_name") or student["last_name"]).strip()

    if not roll_number or not email or not first_name or not last_name:
        return jsonify({"success": False, "message": "Roll number, name, and email are required."}), 400

    duplicate = db.execute(
        """
        SELECT id FROM students
        WHERE (student_number = ? OR user_id IN (SELECT id FROM users WHERE email = ?))
          AND id != ?
        """,
        roll_number,
        email,
        student_id,
    )
    if duplicate:
        return jsonify({"success": False, "message": "Roll number or email already in use."}), 409

    max_credit_hours = student["max_credit_hours"]
    if "max_credit_hours" in data:
        raw_max = data.get("max_credit_hours")
        if raw_max in (None, ""):
            max_credit_hours = None
        else:
            try:
                max_credit_hours = int(raw_max)
                if max_credit_hours < 1:
                    return jsonify({"success": False, "message": "Max credit hours must be at least 1."}), 400
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "Invalid max credit hours value."}), 400

    db.execute(
        """
        UPDATE students
        SET student_number = ?, first_name = ?, last_name = ?, program = ?,
            enrollment_year = ?, department_id = ?, admission_session_id = ?,
            is_active = ?, max_credit_hours = ?
        WHERE id = ?
        """,
        roll_number,
        first_name,
        last_name,
        data.get("program") or None,
        data.get("enrollment_year") or student["enrollment_year"],
        data.get("department_id") or None,
        data.get("admission_session_id") or student["admission_session_id"],
        1 if data.get("is_active", True) else 0,
        max_credit_hours,
        student_id,
    )
    db.execute(
        "UPDATE users SET email = ?, username = ?, is_active = ? WHERE id = ?",
        email,
        roll_number,
        1 if data.get("is_active", True) else 0,
        student["user_id"],
    )

    if data.get("password"):
        db.execute(
            "UPDATE users SET hash = ? WHERE id = ?",
            generate_password_hash(data["password"]),
            student["user_id"],
        )

    log_audit(db, "student_update", "students", student_id)
    return jsonify({"success": True, "message": "Student updated."})


@app.route("/api/admin/students/<int:student_id>/profile")
@login_required
@role_required("admin")
def api_admin_student_profile(student_id):
    """Return a student profile with enrollments, attendance, and fee status."""
    rows = db.execute(
        """
        SELECT s.*, u.email, d.name AS department_name, d.code AS department_code
        FROM students s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE s.id = ?
        """,
        student_id,
    )
    if not rows:
        return jsonify({"success": False, "message": "Student not found."}), 404

    student = rows[0]
    enrollments = db.execute(
        """
        SELECT e.id AS enrollment_id, e.status, e.grade, e.grade_points, e.enrolled_at,
               c.code, c.title, c.credits, c.has_lab, sem.name AS semester_name
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN semesters sem ON c.semester_id = sem.id
        WHERE e.student_id = ? AND e.status != 'dropped'
        ORDER BY sem.start_date DESC, c.code
        """,
        student_id,
    )
    enrollments = [enrich_course_credits(row) for row in enrollments]
    attendance = get_student_attendance(db, student_id)
    fee_data = fetch_student_fees(db, student_id)
    semester = get_active_semester()
    credit_summary = (
        get_student_credit_summary(db, student, semester["id"])
        if semester
        else None
    )

    return jsonify(
        {
            "student": student,
            "cgpa": calculate_gpa(student_id),
            "enrollments": enrollments,
            "attendance": attendance,
            "fees": fee_data,
            "credit_summary": credit_summary,
        }
    )


@app.route("/api/admin/students", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_add_student():
    """Enroll one admitted student, with optional automatic roll number assignment."""
    data = request.get_json(silent=True) or {}
    is_valid, error = validate_add_student_form(data)
    if not is_valid:
        return jsonify({"success": False, "message": error}), 400

    email = data["email"].strip()
    auto_roll = bool(data.get("auto_roll"))
    admission_session_id = data.get("admission_session_id")

    if auto_roll:
        if not admission_session_id:
            return jsonify({"success": False, "message": "Select a Fall or Spring admission session."}), 400
        session_row = get_admission_session(db, int(admission_session_id))
        if not session_row:
            return jsonify({"success": False, "message": "Admission session not found."}), 404
        if not session_row["is_open"]:
            return jsonify({"success": False, "message": "This admission session is closed."}), 403
        roll_number = allocate_roll_number(db, int(admission_session_id))
        enrollment_year = session_row["year"]
    else:
        roll_number = data["roll_number"].strip()
        try:
            enrollment_year = int(data["enrollment_year"])
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid batch year."}), 400
        admission_session_id = admission_session_id or None

    if student_exists(db, roll_number=roll_number, email=email):
        return jsonify({"success": False, "message": "Roll number or email already exists."}), 409

    department_id = data.get("department_id")
    create_student_account(
        roll_number=roll_number,
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=email,
        password=data["password"],
        program=data.get("program"),
        enrollment_year=enrollment_year,
        department_id=department_id,
        admission_session_id=int(admission_session_id) if admission_session_id else None,
    )

    return jsonify(
        {
            "success": True,
            "message": f"Student {roll_number} enrolled successfully.",
            "roll_number": roll_number,
        }
    )


@app.route("/api/admin/students/bulk", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_bulk_students():
    """Bulk-enroll students from JSON rows or a CSV upload for one admission session."""
    admission_session_id = request.form.get("admission_session_id") or (request.get_json(silent=True) or {}).get(
        "admission_session_id"
    )
    default_password = request.form.get("default_password") or (request.get_json(silent=True) or {}).get(
        "default_password", ""
    )

    if not admission_session_id:
        return jsonify({"success": False, "message": "Admission session is required."}), 400

    try:
        admission_session_id = int(admission_session_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid admission session."}), 400

    student_rows = []
    parse_errors = []

    if "csv_file" in request.files and request.files["csv_file"].filename:
        csv_text = request.files["csv_file"].read().decode("utf-8-sig")
        student_rows, parse_errors = parse_students_csv(csv_text)
    else:
        payload = request.get_json(silent=True) or {}
        student_rows = payload.get("students") or []
        if not student_rows:
            return jsonify({"success": False, "message": "Upload a CSV file or provide student rows."}), 400

    if parse_errors:
        return jsonify({"success": False, "message": parse_errors[0], "errors": parse_errors}), 400

    try:
        result = bulk_enroll_students(db, admission_session_id, default_password, student_rows)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    message = (
        f"Imported {result['created_count']} student(s) into {result['session']}."
        if result["created_count"]
        else "No students were imported."
    )
    if result["failed_count"]:
        message += f" {result['failed_count']} row(s) failed."

    return jsonify({"success": True, "message": message, **result})


@app.route("/api/admin/admission-sessions", methods=["GET", "POST"])
@login_required
@role_required("admin")
def api_admin_admission_sessions():
    """List, create, or toggle Fall / Spring admission sessions."""
    if request.method == "GET":
        return jsonify(get_admission_sessions(db))

    data = request.get_json(silent=True) or {}
    action = data.get("action", "create")

    if action == "toggle_open":
        session_id = data.get("session_id")
        current = db.execute("SELECT is_open FROM admission_sessions WHERE id = ?", session_id)
        if not current:
            return jsonify({"success": False, "message": "Admission session not found."}), 404
        new_value = 0 if current[0]["is_open"] else 1
        db.execute("UPDATE admission_sessions SET is_open = ? WHERE id = ?", new_value, session_id)
        status = "opened" if new_value else "closed"
        return jsonify({"success": True, "message": f"Admission session {status}."})

    season = (data.get("season") or "").strip().lower()
    year = data.get("year")

    if season not in ("fall", "spring"):
        return jsonify({"success": False, "message": "Season must be fall or spring."}), 400

    try:
        year = int(year)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Year is required."}), 400

    try:
        session_row = create_admission_session(db, season, year)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    return jsonify(
        {
            "success": True,
            "message": f"{session_row['name']} admission session is ready.",
            "session": session_row,
        }
    )


@app.route("/api/admin/stats")
@login_required
@role_required("admin")
def api_admin_stats():
    """Return live dashboard statistics."""
    refresh_fee_statuses(db)
    return jsonify(
        {
            "students": db.execute(
                "SELECT COUNT(*) AS count FROM students WHERE is_active = 1"
            )[0]["count"],
            "courses": db.execute("SELECT COUNT(*) AS count FROM courses")[0]["count"],
            "pending_fees": db.execute(
                """
                SELECT COUNT(*) AS count FROM student_fees
                WHERE status IN ('pending', 'partial', 'overdue') AND amount_paid < amount
                """
            )[0]["count"],
            "recent_enrollments": db.execute(
                """
                SELECT COUNT(*) AS count FROM enrollments
                WHERE status IN ('enrolled', 'waitlisted')
                  AND enrolled_at >= datetime('now', '-30 days')
                """
            )[0]["count"],
        }
    )


# ── Student profile API ────────────────────────────────────────────────────────


@app.route("/api/student/profile", methods=["PUT"])
@login_required
@role_required("student")
def api_student_profile_update():
    """Update student contact info and optional profile picture."""
    student = require_student_profile(api=True)
    if not student:
        return jsonify({"success": False, "message": "Session expired."}), 401

    phone = (request.form.get("phone") or "").strip() or None
    address = (request.form.get("address") or "").strip() or None
    profile_picture = student.get("profile_picture")

    if "profile_picture" in request.files:
        file = request.files["profile_picture"]
        if file and file.filename:
            ext = secure_filename(file.filename).rsplit(".", 1)[-1].lower()
            if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
                return jsonify({"success": False, "message": "Invalid image format."}), 400
            filename = f"{student['student_number']}_{uuid.uuid4().hex[:8]}.{ext}"
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            profile_picture = f"uploads/profiles/{filename}"

    db.execute(
        "UPDATE students SET phone = ?, address = ?, profile_picture = ? WHERE id = ?",
        phone,
        address,
        profile_picture,
        student["id"],
    )
    log_audit(db, "profile_update", "students", student["id"])
    return jsonify({"success": True, "message": "Profile updated.", "profile_picture": profile_picture})


# ── Admin enrollments, attendance, fees APIs ───────────────────────────────────


@app.route("/api/admin/roster/<int:course_id>/enroll", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_manual_enroll(course_id):
    """Manually enroll a student in a course."""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    if not student_id:
        return jsonify({"success": False, "message": "Student ID required."}), 400

    existing = db.execute(
        "SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?",
        student_id,
        course_id,
    )
    enrolled_count, _ = course_enrollment_counts(course_id)
    course_row = db.execute(
        "SELECT capacity, code, credits, semester_id FROM courses WHERE id = ?",
        course_id,
    )[0]
    status = "enrolled" if enrolled_count < course_row["capacity"] else "waitlisted"
    override_credit = bool(data.get("override_credit_limit"))

    if status == "enrolled" and not override_credit:
        student_rows = db.execute("SELECT * FROM students WHERE id = ?", student_id)
        if student_rows:
            exceeds, credit_msg, _ = would_exceed_credit_limit(
                db, student_rows[0], course_row["semester_id"], course_row["credits"]
            )
            if exceeds:
                return jsonify({"success": False, "message": credit_msg}), 403

    if existing:
        db.execute(
            "UPDATE enrollments SET status = ?, enrolled_at = datetime('now') WHERE id = ?",
            status,
            existing[0]["id"],
        )
    else:
        db.execute(
            "INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, ?)",
            student_id,
            course_id,
            status,
        )
    log_audit(db, "admin_enroll", "enrollments", course_id, {"student_id": student_id, "status": status})
    return jsonify({"success": True, "message": f"Student {status} in {course_row['code']}."})


@app.route("/api/admin/roster/<int:course_id>/drop", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_manual_drop(course_id):
    """Manually drop a student from a course."""
    data = request.get_json(silent=True) or {}
    enrollment_id = data.get("enrollment_id")
    if not enrollment_id:
        return jsonify({"success": False, "message": "Enrollment ID required."}), 400

    enrollment = db.execute(
        """
        SELECT e.id, e.status, c.code
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.id = ? AND e.course_id = ? AND e.status IN ('enrolled', 'waitlisted')
        """,
        enrollment_id,
        course_id,
    )
    if not enrollment:
        return jsonify({"success": False, "message": "Enrollment not found."}), 404

    db.execute("UPDATE enrollments SET status = 'dropped' WHERE id = ?", enrollment_id)
    log_audit(db, "admin_drop", "enrollments", enrollment_id, {"course_id": course_id})
    return jsonify({"success": True, "message": f"Dropped from {enrollment[0]['code']}."})


@app.route("/api/admin/attendance/<int:course_id>")
@login_required
@role_required("admin")
def api_admin_attendance_roster(course_id):
    """Return roster with attendance summary for a course."""
    rows = db.execute(
        """
        SELECT e.id AS enrollment_id, s.student_number, s.first_name, s.last_name, e.status
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        WHERE e.course_id = ? AND e.status IN ('enrolled', 'completed')
        ORDER BY s.student_number
        """,
        course_id,
    )
    result = []
    for row in rows:
        from portal_services import attendance_percentage

        pct, present, total = attendance_percentage(db, row["enrollment_id"])
        sessions = db.execute(
            "SELECT session_date, status FROM attendance_records WHERE enrollment_id = ? ORDER BY session_date",
            row["enrollment_id"],
        )
        result.append({**dict(row), "percentage": pct, "present": present, "total_sessions": total, "sessions": sessions})
    return jsonify(result)


@app.route("/api/admin/attendance", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_attendance_record():
    """Record or update attendance for one enrollment session."""
    data = request.get_json(silent=True) or {}
    enrollment_id = data.get("enrollment_id")
    session_date = (data.get("session_date") or "").strip()
    status = (data.get("status") or "present").strip()

    if not enrollment_id or not session_date:
        return jsonify({"success": False, "message": "Enrollment and date required."}), 400
    if status not in ("present", "absent", "late"):
        return jsonify({"success": False, "message": "Invalid status."}), 400

    existing = db.execute(
        "SELECT id FROM attendance_records WHERE enrollment_id = ? AND session_date = ?",
        enrollment_id,
        session_date,
    )
    if existing:
        db.execute(
            "UPDATE attendance_records SET status = ? WHERE id = ?",
            status,
            existing[0]["id"],
        )
    else:
        db.execute(
            "INSERT INTO attendance_records (enrollment_id, session_date, status) VALUES (?, ?, ?)",
            enrollment_id,
            session_date,
            status,
        )
    log_audit(db, "attendance_record", "attendance_records", enrollment_id, {"date": session_date, "status": status})
    return jsonify({"success": True, "message": "Attendance recorded."})


@app.route("/api/admin/fee-items", methods=["GET", "POST"])
@login_required
@role_required("admin")
def api_admin_fee_items():
    """Manage fee structure items."""
    if request.method == "GET":
        return jsonify(
            db.execute(
                """
                SELECT fi.*, s.name AS semester_name
                FROM fee_items fi
                LEFT JOIN semesters s ON fi.semester_id = s.id
                ORDER BY fi.id DESC
                """
            )
        )

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    amount = data.get("amount")
    if not name or amount is None:
        return jsonify({"success": False, "message": "Name and amount required."}), 400

    item_id = db.execute(
        "INSERT INTO fee_items (name, description, amount, semester_id) VALUES (?, ?, ?, ?)",
        name,
        (data.get("description") or "").strip() or None,
        float(amount),
        data.get("semester_id"),
    )
    log_audit(db, "fee_item_create", "fee_items", item_id)
    return jsonify({"success": True, "message": "Fee item created.", "id": item_id})


@app.route("/api/admin/student-fees", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_assign_fee():
    """Assign a fee to a student."""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    amount = data.get("amount")
    due_date = (data.get("due_date") or "").strip()
    description = (data.get("description") or "").strip()

    if not student_id or amount is None or not due_date or not description:
        return jsonify({"success": False, "message": "All fee fields required."}), 400

    fee_id = db.execute(
        """
        INSERT INTO student_fees (student_id, fee_item_id, description, amount, due_date, semester_id, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        student_id,
        data.get("fee_item_id"),
        description,
        float(amount),
        due_date,
        data.get("semester_id"),
    )
    log_audit(db, "fee_assign", "student_fees", fee_id, {"student_id": student_id})
    return jsonify({"success": True, "message": "Fee assigned.", "id": fee_id})


@app.route("/api/admin/fee-payments", methods=["POST"])
@login_required
@role_required("admin")
def api_admin_record_payment():
    """Record a payment against a student fee."""
    data = request.get_json(silent=True) or {}
    student_fee_id = data.get("student_fee_id")
    amount = data.get("amount")
    if not student_fee_id or amount is None:
        return jsonify({"success": False, "message": "Fee ID and amount required."}), 400

    fee = db.execute("SELECT * FROM student_fees WHERE id = ?", student_fee_id)
    if not fee:
        return jsonify({"success": False, "message": "Fee not found."}), 404

    fee = fee[0]
    payment_amount = float(amount)
    new_paid = round(fee["amount_paid"] + payment_amount, 2)
    if new_paid > fee["amount"]:
        return jsonify({"success": False, "message": "Payment exceeds fee amount."}), 400

    db.execute(
        """
        INSERT INTO fee_payments (student_fee_id, amount, payment_method, reference_no, recorded_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        student_fee_id,
        payment_amount,
        (data.get("payment_method") or "").strip() or None,
        (data.get("reference_no") or "").strip() or None,
        session["user_id"],
    )

    if new_paid >= fee["amount"]:
        status = "paid"
    elif new_paid > 0:
        status = "partial"
    else:
        status = fee["status"]

    db.execute(
        "UPDATE student_fees SET amount_paid = ?, status = ? WHERE id = ?",
        new_paid,
        status,
        student_fee_id,
    )
    log_audit(db, "fee_payment", "fee_payments", student_fee_id, {"amount": payment_amount})
    return jsonify({"success": True, "message": "Payment recorded."})


# ── Error handlers ─────────────────────────────────────────────────────────────


@app.errorhandler(404)
def not_found(error):
    """Render a styled 404 page."""
    return render_template("errors/404.html"), 404


@app.errorhandler(403)
def forbidden(error):
    """Render a styled 403 page."""
    return render_template("errors/403.html"), 403


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("Database not found. Run: python3 init_db.py")
    print("Tip: use python3 run_dev.py for automatic browser reload on file changes.")
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
