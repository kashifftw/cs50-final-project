"""Business helpers for attendance, fees, deadlines, and analytics."""

from datetime import date, datetime
from typing import Any

from catalog import get_max_credit_hours_per_semester, get_setting


def get_university_email_domain(db) -> str:
    """Return configured university email domain."""
    return get_setting(db, "university_email_domain", "university.edu")


def get_student_max_credit_hours(db, student: dict) -> int:
    """
    Return the credit hour cap for a student in one semester.

    Uses the student's custom limit when set; otherwise the system default.
    """
    custom = student.get("max_credit_hours")
    if custom is not None and custom != "":
        try:
            return int(custom)
        except (TypeError, ValueError):
            pass
    return get_max_credit_hours_per_semester(db)


def get_student_enrolled_credits(db, student_id: int, semester_id: int) -> float:
    """Sum credit hours from actively enrolled courses in a semester."""
    row = db.execute(
        """
        SELECT COALESCE(SUM(c.credits), 0) AS total
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ? AND c.semester_id = ? AND e.status = 'enrolled'
        """,
        student_id,
        semester_id,
    )[0]
    return float(row["total"])


def get_student_credit_summary(db, student: dict, semester_id: int) -> dict[str, Any]:
    """Return used, max, and remaining credit hours for enrollment UI."""
    used = get_student_enrolled_credits(db, student["id"], semester_id)
    max_hours = get_student_max_credit_hours(db, student)
    remaining = max(round(max_hours - used, 1), 0)
    return {
        "semester_id": semester_id,
        "used": round(used, 1),
        "max": max_hours,
        "remaining": remaining,
        "is_custom_limit": student.get("max_credit_hours") is not None,
    }


def would_exceed_credit_limit(
    db, student: dict, semester_id: int, additional_credits: float
) -> tuple[bool, str, dict[str, Any]]:
    """
    Check whether enrolling in a course would exceed the student's credit cap.

    Returns (exceeds, error_message, credit_summary).
    """
    summary = get_student_credit_summary(db, student, semester_id)
    projected = summary["used"] + float(additional_credits)
    if projected > summary["max"]:
        message = (
            f"Cannot enroll: exceeds maximum allowed credit hours ({summary['max']})."
        )
        return True, message, summary
    return False, "", summary


def get_upcoming_deadlines(db, semester_id: int | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Return upcoming academic deadlines for the student dashboard."""
    today = date.today().isoformat()
    if semester_id:
        return db.execute(
            """
            SELECT * FROM academic_deadlines
            WHERE due_date >= ? AND audience IN ('all', 'students')
              AND (semester_id IS NULL OR semester_id = ?)
            ORDER BY due_date ASC LIMIT ?
            """,
            today,
            semester_id,
            limit,
        )
    return db.execute(
        """
        SELECT * FROM academic_deadlines
        WHERE due_date >= ? AND audience IN ('all', 'students')
        ORDER BY due_date ASC LIMIT ?
        """,
        today,
        limit,
    )


def attendance_percentage(db, enrollment_id: int) -> tuple[float, int, int]:
    """
    Compute attendance percentage for an enrollment.

    Returns (percentage, present_count, total_sessions).
    """
    rows = db.execute(
        "SELECT status FROM attendance_records WHERE enrollment_id = ?",
        enrollment_id,
    )
    if not rows:
        return 0.0, 0, 0

    total = len(rows)
    present = sum(1 for row in rows if row["status"] in ("present", "late"))
    pct = round((present / total) * 100, 1) if total else 0.0
    return pct, present, total


def get_student_attendance(db, student_id: int, semester_id: int | None = None) -> list[dict[str, Any]]:
    """Return per-course attendance summary for a student."""
    query = """
        SELECT e.id AS enrollment_id, c.code, c.title, c.semester_id, s.name AS semester_name,
               COALESCE(f.name, c.instructor_name) AS instructor_name
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN semesters s ON c.semester_id = s.id
        LEFT JOIN faculty f ON c.faculty_id = f.id
        WHERE e.student_id = ? AND e.status IN ('enrolled', 'completed')
    """
    params: list[Any] = [student_id]
    if semester_id:
        query += " AND c.semester_id = ?"
        params.append(semester_id)
    query += " ORDER BY s.start_date DESC, c.code"

    courses = db.execute(query, *params)
    result = []
    for course in courses:
        pct, present, total = attendance_percentage(db, course["enrollment_id"])
        result.append({**dict(course), "percentage": pct, "present": present, "total_sessions": total})
    return result


def refresh_fee_statuses(db) -> None:
    """Mark overdue fees based on due date."""
    today = date.today().isoformat()
    db.execute(
        """
        UPDATE student_fees
        SET status = 'overdue'
        WHERE status IN ('pending', 'partial') AND due_date < ? AND amount_paid < amount
        """,
        today,
    )


def get_student_fees(db, student_id: int) -> dict[str, Any]:
    """Return fee summary, line items, and payment history for a student."""
    refresh_fee_statuses(db)
    fees = db.execute(
        """
        SELECT sf.*, s.name AS semester_name
        FROM student_fees sf
        LEFT JOIN semesters s ON sf.semester_id = s.id
        WHERE sf.student_id = ?
        ORDER BY sf.due_date DESC
        """,
        student_id,
    )

    payments = db.execute(
        """
        SELECT fp.*, sf.description AS fee_description
        FROM fee_payments fp
        JOIN student_fees sf ON fp.student_fee_id = sf.id
        WHERE sf.student_id = ?
        ORDER BY fp.paid_at DESC
        """,
        student_id,
    )

    total_due = sum(max(f["amount"] - f["amount_paid"], 0) for f in fees)
    overdue = sum(1 for f in fees if f["status"] == "overdue")
    return {"fees": fees, "payments": payments, "total_due": round(total_due, 2), "overdue_count": overdue}
