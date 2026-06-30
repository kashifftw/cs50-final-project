-- University ERP System — Normalized relational schema
-- Run once to initialize: python3 init_db.py

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS fee_payments;
DROP TABLE IF EXISTS student_fees;
DROP TABLE IF EXISTS fee_items;
DROP TABLE IF EXISTS attendance_records;
DROP TABLE IF EXISTS student_queries;
DROP TABLE IF EXISTS password_reset_tokens;
DROP TABLE IF EXISTS academic_deadlines;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS announcements;
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS course_prerequisites;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS faculty;
DROP TABLE IF EXISTS semesters;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS admission_sessions;
DROP TABLE IF EXISTS programs;
DROP TABLE IF EXISTS system_settings;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    department_id INTEGER,
    credits_required INTEGER NOT NULL DEFAULT 120,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE admission_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    season TEXT NOT NULL CHECK (season IN ('fall', 'spring')),
    year INTEGER NOT NULL,
    next_roll_seq INTEGER NOT NULL DEFAULT 1,
    is_open INTEGER NOT NULL DEFAULT 1,
    UNIQUE (season, year)
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    student_number TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    department_id INTEGER,
    program TEXT,
    enrollment_year INTEGER,
    admission_session_id INTEGER,
    phone TEXT,
    address TEXT,
    profile_picture TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    max_credit_hours INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (admission_session_id) REFERENCES admission_sessions(id)
);

CREATE TABLE faculty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department_id INTEGER,
    title TEXT,
    office_hours TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE semesters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    registration_open INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    credits INTEGER NOT NULL DEFAULT 2 CHECK (credits IN (2, 3)),
    has_lab INTEGER NOT NULL DEFAULT 0,
    department_id INTEGER NOT NULL,
    faculty_id INTEGER,
    instructor_name TEXT,
    semester_id INTEGER NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 30,
    schedule_day TEXT,
    schedule_time TEXT,
    room TEXT,
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE SET NULL,
    FOREIGN KEY (semester_id) REFERENCES semesters(id),
    UNIQUE (code, semester_id)
);

CREATE TABLE course_prerequisites (
    course_id INTEGER NOT NULL,
    prerequisite_course_id INTEGER NOT NULL,
    PRIMARY KEY (course_id, prerequisite_course_id),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (prerequisite_course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'enrolled'
        CHECK (status IN ('pending', 'enrolled', 'waitlisted', 'dropped', 'completed')),
    grade TEXT,
    grade_points REAL,
    enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (student_id, course_id)
);

CREATE TABLE attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL,
    session_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'present'
        CHECK (status IN ('present', 'absent', 'late')),
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE,
    UNIQUE (enrollment_id, session_date)
);

CREATE TABLE fee_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    semester_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE SET NULL
);

CREATE TABLE student_fees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    fee_item_id INTEGER,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    amount_paid REAL NOT NULL DEFAULT 0,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'partial', 'paid', 'overdue')),
    semester_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (fee_item_id) REFERENCES fee_items(id) ON DELETE SET NULL,
    FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE SET NULL
);

CREATE TABLE fee_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_fee_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT,
    reference_no TEXT,
    paid_at TEXT NOT NULL DEFAULT (datetime('now')),
    recorded_by INTEGER,
    FOREIGN KEY (student_fee_id) REFERENCES student_fees(id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(id)
);

CREATE TABLE announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    audience TEXT NOT NULL DEFAULT 'all'
        CHECK (audience IN ('all', 'students')),
    course_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (author_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
);

CREATE TABLE academic_deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT NOT NULL,
    semester_id INTEGER,
    audience TEXT NOT NULL DEFAULT 'students'
        CHECK (audience IN ('all', 'students')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE SET NULL
);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE student_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    recipient_type TEXT NOT NULL CHECK (recipient_type IN ('admin', 'faculty')),
    faculty_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'replied', 'closed')),
    admin_reply TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    replied_at TEXT,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE SET NULL
);

CREATE TABLE password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
CREATE INDEX idx_courses_semester ON courses(semester_id);
CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);
CREATE INDEX idx_attendance_enrollment ON attendance_records(enrollment_id);
CREATE INDEX idx_student_fees_student ON student_fees(student_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

-- ── Seed data ────────────────────────────────────────────────────────────────

INSERT INTO departments (code, name) VALUES
    ('CS', 'Computer Science'),
    ('MATH', 'Mathematics'),
    ('BUS', 'Business Administration'),
    ('ENG', 'Engineering'),
    ('BIO', 'Biological Sciences');

INSERT INTO programs (name, department_id, credits_required) VALUES
    ('BSc Computer Science', 1, 120),
    ('BSc Mathematics', 2, 120),
    ('BSc Business Administration', 3, 120),
    ('BEng Engineering', 4, 120),
    ('BSc Biological Sciences', 5, 120),
    ('BA English', NULL, 120),
    ('BSc Economics', 3, 120),
    ('BSc Psychology', NULL, 120);

INSERT INTO system_settings (key, value) VALUES
    ('degree_credits_required', '120'),
    ('portal_name', 'Campus Portal'),
    ('registration_message', 'Course registration is open. Enroll before seats fill up.'),
    ('university_email_domain', 'university.edu'),
    ('self_registration_open', '0'),
    ('max_credit_hours_per_semester', '18');

INSERT INTO semesters (name, start_date, end_date, is_active, registration_open) VALUES
    ('Fall 2025', '2025-08-25', '2025-12-15', 0, 0),
    ('Spring 2026', '2026-01-12', '2026-05-08', 1, 1),
    ('Summer 2026', '2026-06-01', '2026-08-15', 0, 0);

INSERT INTO users (username, email, hash, role) VALUES
    ('admin', 'admin@university.edu', 'pbkdf2:sha256:600000$placeholder$placeholder', 'admin'),
    ('2024-F-001', 'jsmith@university.edu', 'pbkdf2:sha256:600000$placeholder$placeholder', 'student'),
    ('2024-F-002', 'mwong@university.edu', 'pbkdf2:sha256:600000$placeholder$placeholder', 'student');

INSERT INTO admission_sessions (name, season, year, next_roll_seq, is_open) VALUES
    ('Fall 2024', 'fall', 2024, 3, 0),
    ('Spring 2025', 'spring', 2025, 1, 0),
    ('Fall 2025', 'fall', 2025, 1, 1),
    ('Spring 2026', 'spring', 2026, 1, 1);

INSERT INTO students (user_id, student_number, first_name, last_name, department_id, program, enrollment_year, admission_session_id, phone) VALUES
    (2, '2024-F-001', 'John', 'Smith', 1, 'BSc Computer Science', 2024, 1, '+1 555-0101'),
    (3, '2024-F-002', 'Maria', 'Wong', 2, 'BSc Mathematics', 2024, 1, '+1 555-0102');

INSERT INTO faculty (name, email, department_id, title, office_hours) VALUES
    ('David Lee', 'dlee@university.edu', 1, 'Associate Professor', 'Mon/Wed 2–4 PM'),
    ('Kavita Patel', 'kpatel@university.edu', 2, 'Professor', 'Tue/Thu 1–3 PM'),
    ('James Rivera', 'jrivera@university.edu', 3, 'Lecturer', 'Fri 10 AM–12 PM');

INSERT INTO courses (code, title, description, credits, has_lab, department_id, faculty_id, instructor_name, semester_id, capacity, schedule_day, schedule_time, room) VALUES
    ('CS50', 'Introduction to Computer Science', 'Foundational programming and computational thinking (lecture and lab).', 3, 1, 1, 1, 'David Lee', 2, 120, 'Mon/Wed/Fri', '10:00–11:00', 'Science Hall 101'),
    ('CS101', 'Data Structures & Algorithms', 'Arrays, trees, graphs, sorting, and algorithmic analysis (lecture and lab).', 3, 1, 1, 1, 'David Lee', 2, 60, 'Tue/Thu', '13:00–14:30', 'CS Building 301'),
    ('CS201', 'Database Systems', 'Relational design, SQL, normalization, and transaction management (lecture and lab).', 3, 1, 1, 1, 'David Lee', 2, 40, 'Mon/Wed', '14:00–15:30', 'CS Building 205'),
    ('MATH101', 'Calculus I', 'Limits, derivatives, integrals, and applications.', 2, 0, 2, 2, 'Kavita Patel', 2, 80, 'Mon/Wed/Fri', '09:00–10:00', 'Math Hall 201'),
    ('MATH201', 'Linear Algebra', 'Vector spaces, matrices, eigenvalues, and linear transformations.', 2, 0, 2, 2, 'Kavita Patel', 2, 50, 'Tue/Thu', '11:00–12:30', 'Math Hall 105'),
    ('BUS110', 'Introduction to Business', 'Overview of business functions, ethics, and global markets.', 2, 0, 3, 3, 'James Rivera', 2, 100, 'Mon/Wed', '11:00–12:30', 'Business School 110'),
    ('ENG150', 'Engineering Fundamentals', 'Problem-solving, design process, and technical communication.', 2, 0, 4, NULL, 'TBA', 2, 75, 'Tue/Thu', '15:00–16:30', 'Engineering Hall 1'),
    ('BIO101', 'General Biology', 'Cell structure, genetics, evolution, and ecology (lecture and lab).', 3, 1, 5, NULL, 'TBA', 2, 90, 'Mon/Wed/Fri', '13:00–14:00', 'Life Sciences 220');

INSERT INTO course_prerequisites (course_id, prerequisite_course_id) VALUES (2, 1);
INSERT INTO course_prerequisites (course_id, prerequisite_course_id) VALUES (3, 2);
INSERT INTO course_prerequisites (course_id, prerequisite_course_id) VALUES (5, 4);

INSERT INTO courses (code, title, description, credits, has_lab, department_id, faculty_id, instructor_name, semester_id, capacity, schedule_day, schedule_time, room) VALUES
    ('CS50-F25', 'Introduction to Computer Science', 'Foundational programming (Fall 2025 archive, lecture and lab).', 3, 1, 1, 1, 'David Lee', 1, 120, 'Mon/Wed/Fri', '10:00–11:00', 'Science Hall 101');

INSERT INTO enrollments (student_id, course_id, status, grade, grade_points) VALUES
    (1, 9, 'completed', 'A', 4.0);

INSERT INTO enrollments (student_id, course_id, status) VALUES
    (1, 4, 'enrolled'),
    (2, 4, 'enrolled'),
    (2, 8, 'enrolled');

INSERT INTO attendance_records (enrollment_id, session_date, status) VALUES
    (2, '2026-01-15', 'present'),
    (2, '2026-01-17', 'present'),
    (2, '2026-01-20', 'absent'),
    (2, '2026-01-22', 'present'),
    (2, '2026-01-24', 'late'),
    (3, '2026-01-15', 'present'),
    (3, '2026-01-17', 'present'),
    (3, '2026-01-20', 'present'),
    (4, '2026-01-16', 'present'),
    (4, '2026-01-18', 'absent');

INSERT INTO fee_items (name, description, amount, semester_id) VALUES
    ('Tuition — Spring 2026', 'Semester tuition', 4500.00, 2),
    ('Student Activity Fee', 'Campus activities and clubs', 150.00, 2),
    ('Lab Fee — CS', 'Computer science lab access', 200.00, 2);

INSERT INTO student_fees (student_id, fee_item_id, description, amount, amount_paid, due_date, status, semester_id) VALUES
    (1, 1, 'Tuition — Spring 2026', 4500.00, 4500.00, '2026-01-31', 'paid', 2),
    (1, 2, 'Student Activity Fee', 150.00, 150.00, '2026-01-31', 'paid', 2),
    (1, 3, 'Lab Fee — CS', 200.00, 100.00, '2026-02-15', 'partial', 2),
    (2, 1, 'Tuition — Spring 2026', 4500.00, 0, '2026-01-31', 'overdue', 2),
    (2, 2, 'Student Activity Fee', 150.00, 0, '2026-01-31', 'overdue', 2);

INSERT INTO fee_payments (student_fee_id, amount, payment_method, reference_no, recorded_by) VALUES
    (1, 4500.00, 'Bank Transfer', 'TXN-2026-001', 1),
    (2, 150.00, 'Credit Card', 'TXN-2026-002', 1),
    (3, 100.00, 'Credit Card', 'TXN-2026-003', 1);

INSERT INTO academic_deadlines (title, description, due_date, semester_id, audience) VALUES
    ('Add/Drop Deadline', 'Last day to add or drop courses without penalty', '2026-01-24', 2, 'students'),
    ('Midterm Examinations', 'Midterm week — check course syllabi for schedules', '2026-03-12', 2, 'students'),
    ('Tuition Payment Due', 'Final date for Spring 2026 tuition payment', '2026-01-31', 2, 'students'),
    ('Final Project Submission', 'CS201 database project due', '2026-04-20', 2, 'students');

INSERT INTO announcements (title, content, author_id, audience) VALUES
    ('Spring 2026 Registration Open', 'Course registration for Spring 2026 is now open. Enroll before seats fill up.', 1, 'students'),
    ('Midterm Week Schedule', 'Midterm examinations run March 10–14. Check your course syllabi for room assignments.', 1, 'all');

INSERT INTO notifications (user_id, message, link) VALUES
    (2, 'Welcome to Campus Portal! Explore courses and build your schedule.', '/student/dashboard'),
    (2, 'You are enrolled in MATH101 — Calculus I.', '/student/schedule'),
    (3, 'Welcome to Campus Portal! Registration for Spring 2026 is open.', '/student/courses');

INSERT INTO student_queries (student_id, subject, message, recipient_type, faculty_id, status) VALUES
    (1, 'Grade inquiry — CS50', 'Could you clarify the grading breakdown for the final project?', 'faculty', 1, 'open'),
    (2, 'Transcript request', 'I need an official transcript sent to my internship employer.', 'admin', NULL, 'open');
