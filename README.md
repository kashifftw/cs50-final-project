# University ERP — Campus Portal

**CS50 Final Project**

**Demo video:** [https://youtu.be/PLACEHOLDER](https://youtu.be/PLACEHOLDER) *(replace with your unlisted YouTube URL before submission)*

---

## Video opening slide (required)

Use this information on the first slide of your ≤3 minute demo video:

| Field | Value |
|-------|-------|
| **Project title** | University ERP — Campus Portal |
| **Your name** | *[Your full name]* |
| **GitHub username** | kashifftw |
| **edX username** | *[your-edx-username]* |
| **City and country** | *[City, Country]* |
| **Date of recording** | *[YYYY-MM-DD]* |

---

## What this application does

University ERP is a full-stack web application that models a small university’s day-to-day operations through two role-based portals: a **student portal** and an **admin console**. Students sign in with a roll number and password to view their dashboard, academic record, course registration, enrollments, weekly schedule, attendance, and fee status. Administrators manage the catalog of courses, enroll and drop students (with optional credit-limit overrides), record grades and attendance, publish announcements, configure which student portal sections are visible, and admit new students individually or in bulk via CSV.

The system enforces realistic academic rules: courses are either two-credit theory-only offerings or three-credit theory-plus-lab subjects (stored as a single course with a `has_lab` flag), students face a default semester credit cap of eighteen hours (with per-student admin overrides), and prerequisites are checked before enrollment. Fees can be issued, partially paid, and marked overdue automatically. An audit log records sensitive admin actions for traceability.

Authentication uses Flask server-side sessions with hashed passwords (Werkzeug PBKDF2). Students cannot self-register; admission is admin-driven through admission sessions that allocate formatted roll numbers (for example `2024-F-001`). Password reset flows exist for university-domain emails. The UI uses a shared **Aurora** dark theme across student, admin, and login pages, with responsive layouts and client-side enhancements via vanilla JavaScript calling JSON API endpoints.

---

## How to run

### Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # optional; app runs without .env using dev defaults
python3 init_db.py      # creates university.db with seeded demo data
python3 run_dev.py      # or: flask run
```

Open the URL printed in the terminal (default port 5000, or next free port).

### Demo accounts

| Role | Username | Password |
|------|----------|----------|
| Student | `2024-F-001` | `student123` |
| Student | `2024-F-002` | `student123` |
| Admin | `admin` | `admin123` |

Student login: `/login` — Admin login: `/admin/login`

### Database for graders

**Run `python3 init_db.py` fresh.** The repository intentionally does **not** ship `university.db` (it is listed in `.gitignore`). The grader should always initialize from `schema.sql` via `init_db.py`, which creates tables, inserts seed data, hashes demo passwords, and writes default portal section settings. Do not rely on a pre-built database file from the author’s machine.

---

## submit50 checklist

Before running `submit50`, ensure your zip does **not** include:

| Item | Status in repo | Action before submit |
|------|----------------|----------------------|
| `__pycache__/` | Gitignored; may exist locally after running the app | **Delete manually:** `rm -rf __pycache__` |
| `.env` | Gitignored | **Do not submit** — use `.env.example` only |
| `university.db` | Gitignored | **Do not submit** — grader runs `init_db.py` |
| `static/uploads/profiles/*` | Gitignored (except `.gitkeep`) | Remove any uploaded profile images |

`.gitignore` already excludes these paths from Git; `submit50` zips the folder on disk, so local artifacts must be removed manually.

---

## Project structure — what each file does

### Application core

| File | Purpose |
|------|---------|
| `app.py` | Flask entry point: routes, session auth, HTML pages, and JSON APIs for students and admins |
| `database.py` | SQLite access wrapper returning dict-like rows |
| `schema.sql` | Full relational schema plus seed departments, programs, courses, students, and sample records |
| `init_db.py` | Builds `university.db` from `schema.sql` and applies real password hashes |
| `run_dev.py` | Development server with LiveReload on templates, static files, and Python changes |
| `requirements.txt` | Python dependencies (Flask, SQLAlchemy, Werkzeug, python-dotenv, livereload) |

### Domain and business logic

| File | Purpose |
|------|---------|
| `admission.py` | Admission sessions, roll-number allocation, single and bulk student enrollment |
| `catalog.py` | Departments, programs, degree credit requirements, and key-value system settings |
| `portal_config.py` | Which student portal sections are enabled and their navigation labels |
| `portal_services.py` | Credit summaries, attendance queries, fee status refresh, registration deadlines |
| `portal_format.py` | Display helpers for credits, semester names, and dates |
| `helpers.py` | `login_required` / `role_required` decorators and shared form validation |
| `validators.py` | University email and password strength checks |
| `audit.py` | Writes admin actions to the `audit_log` table |

### Static assets — CSS

| File | Purpose |
|------|---------|
| `static/css/style.css` | Base layout, forms, tables, and shared components |
| `static/css/aurora-theme.css` | Shared dark “Aurora” palette (violet/cyan accents) for all portals |
| `static/css/student-portal.css` | Student dashboard widgets, icon navigation, and responsive grid |
| `static/css/admin-portal.css` | Admin sidebar and console-specific styling |

### Static assets — JavaScript

| File | Purpose |
|------|---------|
| `static/js/app.js` | Shared `UniERP` helpers (API fetch, toasts, modal utilities) |
| `static/js/auth.js` | Login form UX |
| `static/js/student-portal.js` | Student enrollment list interactions |
| `static/js/student-profile.js` | Profile picture upload and edit |
| `static/js/courses.js` | Course catalog search, prerequisite display, add/drop |
| `static/js/admin.js` | Course CRUD, prerequisites multi-select, dashboard actions |
| `static/js/admin-users.js` | Student list, detail drawer, manual enroll/drop, bulk CSV import |
| `static/js/admin-fees.js` | Fee issuance and payment recording |
| `static/js/admin-attendance.js` | Bulk attendance entry for a course offering |

### Templates

| Path | Purpose |
|------|---------|
| `templates/layout.html` | Admin and auth base layout (Aurora theme) |
| `templates/login.html`, `admin_login.html` | Student and admin sign-in |
| `templates/forgot_password.html`, `reset_password.html` | Password recovery flow |
| `templates/student/layout.html` | Student shell with top profile menu and icon nav |
| `templates/student/_icon_nav.html` | Left icon navigation driven by enabled portal sections |
| `templates/student/dashboard.html` | CGPA, registrations, announcements, deadlines |
| `templates/student/*.html` | Profile, academics, courses, enrollments, schedule, attendance, fees |
| `templates/admin/_sidebar.html` | Admin navigation |
| `templates/admin/*.html` | Dashboard, students, courses, enrollments, attendance, fees, announcements, portal settings |
| `templates/errors/403.html`, `404.html` | HTTP error pages |

### Other

| File | Purpose |
|------|---------|
| `samples/bulk_students_sample.csv` | Example CSV for admin bulk admission |
| `.env.example` | Template environment variables (safe to submit) |
| `.gitignore` | Excludes secrets, database, caches, uploads, and screenshots |

---

## Design decisions

**Flask with server-rendered HTML plus JSON APIs.** Pages are rendered with Jinja2 for fast initial load and SEO-friendly structure, while interactive actions (enroll, grade, pay fee) use `fetch` against `/api/*` routes. This split keeps the frontend simple without a heavy JavaScript framework, which suits CS50’s focus on fundamentals.

**SQLite and a thin database module.** A single-file database is easy for graders to reset with `init_db.py`. SQLAlchemy is used only in `init_db.py` for script convenience; runtime queries go through a small `Database` class to keep dependencies light and SQL visible in `app.py`.

**Normalized schema with explicit academic rules.** Courses, enrollments, grades, attendance, fees, and prerequisites live in separate tables with foreign keys. Credit hours derive from course type (`has_lab`) rather than a free-form integer, reducing data-entry errors. The eighteen-credit semester cap is enforced in application code with an admin override path for exceptions.

**Configurable student portal.** Admins toggle sections (for example hide Schedule during maintenance) without code changes. Settings persist in `system_settings` as JSON, merged with defaults in `portal_config.py`.

**Admin-only admission.** Removing public self-registration reflects real university policy: identity and roll numbers are issued by the institution. Bulk CSV import supports orientation-week scale.

**Aurora dark theme.** A single shared stylesheet keeps student and admin experiences visually consistent. Theme toggles were removed in favor of a fixed professional dark UI suitable for long study sessions.

**Security posture for development.** Session cookies rely on `SECRET_KEY` from the environment when set. If `.env` is missing, a hardcoded development fallback is used (see limitations below). Passwords are never stored in plain text.

---

## Known limitations

1. **`SECRET_KEY` fallback.** In `app.py`, if `SECRET_KEY` is not set in the environment, the app uses `dev-unierp-secret-change-in-production`. This is intentional for local CS50 development only. In production you must set a strong random `SECRET_KEY` in `.env`; the fallback should never be used on a public server.

2. **No email delivery.** Password reset tokens are created in the database; actual SMTP sending is not implemented (demo displays or logs would be needed for full production use).

3. **Single-machine deployment.** The app is designed for one Flask process and one SQLite file, not horizontal scaling.

---

## Author

GitHub: [kashifftw](https://github.com/kashifftw) — Repository: [cs50-final-project](https://github.com/kashifftw/cs50-final-project)
