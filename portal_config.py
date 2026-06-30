"""Student portal section visibility — managed from the admin console."""

import json

from catalog import get_setting, set_setting

DEFAULT_PORTAL_SECTIONS = {
    "dashboard": {"enabled": True, "label": "Dashboard"},
    "profile": {"enabled": True, "label": "Profile"},
    "academics": {"enabled": True, "label": "Academics"},
    "courses": {"enabled": True, "label": "Registration"},
    "enrollments": {"enabled": True, "label": "Enrollments"},
    "schedule": {"enabled": True, "label": "Schedule"},
    "attendance": {"enabled": True, "label": "Attendance"},
    "fees": {"enabled": True, "label": "Fees"},
}

SECTION_ENDPOINTS = {
    "dashboard": "student_dashboard",
    "profile": "student_profile",
    "academics": "student_academics",
    "courses": "student_courses",
    "enrollments": "student_enrollments",
    "schedule": "student_schedule",
    "attendance": "student_attendance",
    "fees": "student_fees",
}


def get_portal_sections(db) -> dict:
    """Return portal section config merged with defaults."""
    raw = get_setting(db, "portal_sections", "")
    if not raw:
        return dict(DEFAULT_PORTAL_SECTIONS)

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return dict(DEFAULT_PORTAL_SECTIONS)

    merged = dict(DEFAULT_PORTAL_SECTIONS)
    for key, defaults in DEFAULT_PORTAL_SECTIONS.items():
        if key in stored and isinstance(stored[key], dict):
            merged[key] = {
                **defaults,
                **stored[key],
                "enabled": bool(stored[key].get("enabled", defaults["enabled"])),
            }
    return merged


def save_portal_sections(db, sections: dict) -> None:
    """Persist portal section toggles and labels."""
    merged = get_portal_sections(db)
    for key in DEFAULT_PORTAL_SECTIONS:
        if key in sections and isinstance(sections[key], dict):
            merged[key] = {
                **merged[key],
                "enabled": bool(sections[key].get("enabled", merged[key]["enabled"])),
                "label": (sections[key].get("label") or merged[key]["label"]).strip(),
            }
    set_setting(db, "portal_sections", json.dumps(merged))


def section_enabled(db, section_key: str) -> bool:
    """Return whether a student portal section is enabled."""
    sections = get_portal_sections(db)
    entry = sections.get(section_key)
    return bool(entry and entry.get("enabled", True))


def enabled_sections(db) -> list[dict]:
    """Return enabled sections with route metadata for navigation templates."""
    sections = get_portal_sections(db)
    result = []
    for key, meta in sections.items():
        if not meta.get("enabled", True):
            continue
        endpoint = SECTION_ENDPOINTS.get(key)
        if not endpoint:
            continue
        result.append(
            {
                "key": key,
                "label": meta.get("label", key.title()),
                "endpoint": endpoint,
            }
        )
    return result
