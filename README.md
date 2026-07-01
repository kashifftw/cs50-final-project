# University ERP — Campus Portal

**CS50 Final Project**

**Demo video:** [https://youtu.be/QWPnKI2lLXc](https://youtu.be/QWPnKI2lLXc)

| | |
|---|---|
| **Name** | Kashif Tariq |
| **GitHub** | [kashifftw](https://github.com/kashifftw) |
| **edX** | kashifftw |
| **Location** | Lahore, Pakistan |
| **Recorded** | 2026-07-01 |

---

## Description

University ERP — Campus Portal is a full-stack web application for a small university. It provides a **student portal** for self-service academic tasks and an **admin console** for registrar-style management. The stack is **Python (Flask)**, **SQLite**, **Jinja2** templates, and **vanilla JavaScript** calling JSON API endpoints.

### Student portal

Students sign in with **admission session** (Fall or Spring + batch year), **degree program**, **roll number**, and password. There is no public self-registration; accounts are created by administrators.

Students can:

- View a dashboard (CGPA, credits, enrollments, announcements, deadlines)
- Register for and drop courses when the semester registration window is open
- View academics (transcript, semester GPA, degree progress)
- View enrollments, class schedule, attendance summaries, and fee status
- Update limited profile fields (contact info and profile picture)

Enrollment enforces **prerequisites**, a **semester credit-hour cap** (default 18, with per-student admin override), **course capacity**, and **waitlisting** when a section is full.

### Admin console

Administrators sign in with username and password and can:

- Admit students individually or in bulk via CSV (Fall/Spring admission sessions with auto-generated roll numbers)
- Manage students, courses, departments, programs, and semesters
- Enroll or drop students on course rosters (with optional credit-limit override)
- Issue fees, record payments, and publish announcements
- Toggle which sections appear in the student portal

Sensitive admin actions are written to an **audit log**. Passwords are stored hashed (Werkzeug PBKDF2). Session-based authentication separates student and admin roles.

### Design highlights

- **Server-rendered pages + JSON APIs** — HTML from Jinja2 for fast loads; `fetch` for enroll, drop, and admin CRUD without a heavy frontend framework
- **Normalized SQLite schema** — users, students, courses, enrollments, fees, grades, attendance, prerequisites, and settings in related tables
- **Credit rules in code** — theory-only courses are 2 credits; theory + lab courses are 3 credits (`has_lab` flag); limits enforced at enrollment time
- **Configurable student portal** — admins enable or disable nav sections without code changes (`portal_config.py` + `system_settings`)
- **Dark ERP theme** — shared styling across student, admin, and auth pages (`portal-theme.css`, `student-portal.css`, `auth.css`)

---

## How to run

### Requirements

- Python 3.10+
- Packages in `requirements.txt`

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # optional
python3 init_db.py      # creates university.db from schema.sql
python3 run_dev.py
```

Open the URL printed in the terminal (default port 5000, or the next free port).

### Demo accounts

**Student** — `/login`

| Field | Value |
|-------|--------|
| Session | Fall + `24` |
| Degree | BSCS |
| Roll # | `001` |
| Password | `student123` |

(Stored roll number: `2024-F-001`)

**Admin** — `/login/admin`

| Username | Password |
|----------|----------|
| `admin` | `admin123` |

### Database for graders

**Run `python3 init_db.py` fresh.** The repository does not include `university.db` (it is in `.gitignore`). `init_db.py` applies `schema.sql`, seeds demo data, hashes passwords, and writes default portal settings.

---

## Project structure

| File / folder | Purpose |
|---------------|---------|
| `app.py` | Flask routes, session auth, HTML pages, JSON APIs |
| `database.py` | SQLite access wrapper (dict-like rows) |
| `schema.sql` | Database schema and seed data |
| `init_db.py` | Build `university.db` from `schema.sql` |
| `run_dev.py` | Dev server with LiveReload |
| `admission.py` | Admission sessions, roll numbers, bulk CSV import |
| `catalog.py` | Departments, programs, system settings |
| `portal_config.py` | Student portal section toggles |
| `portal_services.py` | Credit summaries, attendance, fees helpers |
| `portal_format.py` | Display helpers (credits, dates) |
| `helpers.py` | Auth decorators and validation |
| `validators.py` | Email and password checks |
| `audit.py` | Admin audit logging |
| `static/css/` | `style.css`, `portal-theme.css`, `student-portal.css`, `auth.css`, `motion.css` |
| `static/js/` | `app.js`, `auth.js`, `courses.js`, `student-portal.js`, `admin.js`, `admin-users.js`, `admin-fees.js` |
| `templates/` | Jinja2 HTML for auth, student portal, and admin console |
| `samples/bulk_students_sample.csv` | Example CSV for bulk admission |

---

## Design decisions

**Flask + Jinja2 + fetch.** Keeps the frontend simple while still allowing async enrollment and admin actions. Fits CS50’s focus on fundamentals without React or similar frameworks.

**SQLite + thin `Database` class.** One file is easy for graders to reset. SQL remains visible in `app.py` and domain modules.

**Admin-only admission.** Roll numbers (e.g. `2024-F-001`) are issued through admission sessions, matching real university policy.

**Academic rules in application code.** Prerequisites, credit caps, waitlists, and registration windows are enforced server-side, not only in the UI.

**Portal section toggles.** Admins can hide parts of the student interface (e.g. schedule during maintenance) via settings stored as JSON.

---

## Known limitations

1. **`SECRET_KEY` fallback** — If `.env` is missing, a development default is used in `app.py`. Set a strong `SECRET_KEY` in production.
2. **No email delivery** — Password-reset tokens are stored in the database; SMTP is not implemented.
3. **Grades and attendance** — Students can view seeded records; there is no admin UI to enter new grades or attendance in the current version.
4. **Single-machine deployment** — One Flask process and one SQLite file; not designed for horizontal scaling.

---

## Before `submit50`

Remove from the project folder (not tracked by Git, but may exist locally):

```bash
rm -rf __pycache__
rm -f university.db .env
```

Do **not** submit `.env`, `university.db`, or `__pycache__/`.

---

## Author

**Kashif Tariq** — GitHub: [kashifftw](https://github.com/kashifftw) — Repository: [cs50-final-project](https://github.com/kashifftw/cs50-final-project)
