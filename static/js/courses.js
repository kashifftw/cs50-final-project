/**
 * UniERP — Async course catalog, enrollment, and drop actions.
 */

const CourseCatalog = {
    debounceTimer: null,
    creditHours: null,

    init() {
        this.container = document.getElementById('course-results');
        this.searchInput = document.getElementById('course-search');
        this.deptFilter = document.getElementById('filter-department');
        this.semesterFilter = document.getElementById('filter-semester');
        this.creditBanner = document.getElementById('credit-hours-banner');

        if (!this.container) return;

        this.searchInput?.addEventListener('input', () => this.debouncedLoad());
        this.deptFilter?.addEventListener('change', () => this.loadCourses());
        this.semesterFilter?.addEventListener('change', () => {
            this.loadCreditHours().then(() => this.loadCourses());
        });

        this.loadCreditHours().then(() => this.loadCourses());
    },

    debouncedLoad() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.loadCourses(), 300);
    },

    async loadCreditHours() {
        const sem = this.semesterFilter?.value;
        if (!sem || !this.creditBanner) {
            this.creditHours = null;
            this.creditBanner.style.display = 'none';
            return;
        }

        try {
            this.creditHours = await UniERP.apiFetch(`/api/student/credit-hours?semester_id=${sem}`);
            this.renderCreditBanner();
        } catch (_) {
            this.creditHours = null;
            this.creditBanner.style.display = 'none';
        }
    },

    renderCreditBanner() {
        if (!this.creditBanner || !this.creditHours) return;

        const { used, max, remaining, is_custom_limit } = this.creditHours;
        const atLimit = remaining <= 0;
        const customNote = is_custom_limit ? ' <span class="portal-credit-custom">(custom limit)</span>' : '';

        this.creditBanner.className = `portal-credit-banner ${atLimit ? 'portal-credit-banner--full' : ''}`;
        this.creditBanner.innerHTML = `
            <strong>${used}/${max} credit hours used</strong>
            <span>${remaining} remaining this semester${customNote}</span>
        `;
        this.creditBanner.style.display = 'flex';
    },

    wouldExceedCredits(courseCredits) {
        if (!this.creditHours) return false;
        return Number(courseCredits) > Number(this.creditHours.remaining);
    },

    async loadCourses() {
        const params = new URLSearchParams();
        const q = this.searchInput?.value.trim();
        const dept = this.deptFilter?.value;
        const sem = this.semesterFilter?.value;

        if (q) params.set('q', q);
        if (dept) params.set('department_id', dept);
        if (sem) params.set('semester_id', sem);

        this.container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading courses…</div>';

        try {
            const courses = await UniERP.apiFetch(`/api/courses?${params}`);
            this.renderCourses(courses);
        } catch (err) {
            this.container.innerHTML = `<div class="empty-state">${err.message}</div>`;
        }
    },

    renderCourses(courses) {
        if (!courses.length) {
            this.container.innerHTML = '<div class="glass-card"><div class="empty-state"><p>No courses match your search criteria.</p></div></div>';
            return;
        }

        this.container.innerHTML = `<div class="course-grid">${courses.map(c => this.courseCard(c)).join('')}</div>`;

        UniERP.animateStagger(this.container, '.course-card');
        this.container.querySelectorAll('.seats-fill').forEach((bar) => {
            requestAnimationFrame(() => bar.classList.add('is-animated'));
        });

        this.container.querySelectorAll('[data-enroll]').forEach(btn => {
            btn.addEventListener('click', () => this.enroll(parseInt(btn.dataset.enroll), btn));
        });
        this.container.querySelectorAll('[data-drop]').forEach(btn => {
            btn.addEventListener('click', () => this.drop(parseInt(btn.dataset.drop), btn));
        });
    },

    courseCard(course) {
        const fillPct = Math.min((course.enrolled_count / course.capacity) * 100, 100);
        const isFull = course.seats_available === 0;
        const creditBlocked = this.wouldExceedCredits(course.credits);

        let prereqHtml = '';
        if (course.prerequisites?.length) {
            prereqHtml = `<div class="prereq-list">Prerequisites: ${course.prerequisites.map(p =>
                `<span class="${p.met ? 'prereq-met' : 'prereq-unmet'}">${p.code}${p.met ? ' ✓' : ' ✗'}</span>`
            ).join(', ')}</div>`;
        }

        let actionBtn = '';
        if (course.enrollment_status === 'enrolled') {
            actionBtn = `<button class="btn btn-danger btn-sm" data-drop="${course.id}">Drop</button>`;
        } else if (course.enrollment_status === 'waitlisted') {
            actionBtn = `<button class="btn btn-danger btn-sm" data-drop="${course.id}">Leave Waitlist</button>`;
        } else if (course.registration_open) {
            const canEnroll = course.prerequisites_met !== false && !creditBlocked;
            let disabledTitle = '';
            if (course.prerequisites_met === false) disabledTitle = 'Prerequisites not met';
            else if (creditBlocked) disabledTitle = `Exceeds credit hour limit (${this.creditHours?.max || 18})`;
            actionBtn = `<button class="btn btn-primary btn-sm" data-enroll="${course.id}" ${canEnroll ? '' : `disabled title="${disabledTitle}"`}>${isFull ? 'Join Waitlist' : 'Enroll'}</button>`;
        } else {
            actionBtn = `<button class="btn btn-ghost btn-sm" disabled>Registration Closed</button>`;
        }

        let statusBadge = '';
        if (course.enrollment_status === 'enrolled') statusBadge = '<span class="badge badge-emerald">Enrolled</span>';
        else if (course.enrollment_status === 'waitlisted') statusBadge = '<span class="badge badge-amber">Waitlisted</span>';

        return `
            <div class="course-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div class="course-code">${course.code}</div>
                    ${statusBadge}
                </div>
                <div class="course-title">${course.title}</div>
                <div class="course-meta">
                    <span class="course-credit-badge">${course.credits_label || `${course.credits} cr`}</span>
                    <span>${course.department_code}</span>
                    <span>${course.schedule_day || 'TBA'} ${course.schedule_time || ''}</span>
                    <span>${course.room || 'TBA'}</span>
                </div>
                ${course.instructor_name ? `<div style="font-size:0.75rem;color:var(--text-muted);">${course.instructor_name}</div>` : ''}
                <p style="font-size:0.8125rem;color:var(--text-secondary);line-height:1.5;">${course.description || ''}</p>
                ${prereqHtml}
                <div>
                    <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-muted);">
                        <span>${course.enrolled_count}/${course.capacity} enrolled</span>
                        <span>${course.waitlisted_count} waitlisted</span>
                    </div>
                    <div class="seats-bar"><div class="seats-fill ${isFull ? 'full' : ''}" data-seats="${fillPct}" style="--seats-width:${fillPct}%"></div></div>
                </div>
                <div class="course-actions">${actionBtn}</div>
            </div>
        `;
    },

    async enroll(courseId, button) {
        UniERP.setButtonLoading(button, true);
        try {
            const data = await UniERP.apiFetch('/api/enroll', {
                method: 'POST',
                body: JSON.stringify({ course_id: courseId }),
            });
            UniERP.showToast(data.message, 'success');
            await this.loadCreditHours();
            await this.loadCourses();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        } finally {
            UniERP.setButtonLoading(button, false);
        }
    },

    async drop(courseId, button) {
        if (!confirm('Are you sure you want to drop this course?')) return;
        UniERP.setButtonLoading(button, true);
        try {
            const data = await UniERP.apiFetch('/api/drop', {
                method: 'POST',
                body: JSON.stringify({ course_id: courseId }),
            });
            UniERP.showToast(data.message, 'success');
            await this.loadCreditHours();
            await this.loadCourses();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        } finally {
            UniERP.setButtonLoading(button, false);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => CourseCatalog.init());
