/**
 * UniERP — Student portal: enrollments list, filters, and drop actions.
 */

const StudentPortal = {
    allEnrollments: [],

    init() {
        this.listEl = document.getElementById('enrollment-list');
        this.statsEl = document.getElementById('enrollment-stats');
        this.semesterFilter = document.getElementById('enrollment-semester-filter');
        this.statusFilter = document.getElementById('enrollment-status-filter');

        if (!this.listEl) return;

        this.semesterFilter?.addEventListener('change', () => this.loadEnrollments());
        this.statusFilter?.addEventListener('change', () => this.renderFiltered());

        this.loadEnrollments();
    },

    async loadEnrollments() {
        this.listEl.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading enrollments…</div>';

        const params = new URLSearchParams();
        const semesterId = this.semesterFilter?.value;
        if (semesterId) params.set('semester_id', semesterId);

        try {
            this.allEnrollments = await UniERP.apiFetch(`/api/student/enrollments?${params}`);
            this.renderFiltered();
        } catch (err) {
            this.listEl.innerHTML = `<div class="empty-state">${err.message}</div>`;
        }
    },

    renderFiltered() {
        const status = this.statusFilter?.value || '';
        const filtered = status
            ? this.allEnrollments.filter((item) => item.status === status)
            : this.allEnrollments;

        this.renderStats(filtered);
        this.renderList(filtered);
    },

    renderStats(enrollments) {
        if (!this.statsEl) return;

        const enrolled = enrollments.filter((e) => e.status === 'enrolled').length;
        const waitlisted = enrollments.filter((e) => e.status === 'waitlisted').length;
        const completed = enrollments.filter((e) => e.status === 'completed').length;
        const credits = enrollments
            .filter((e) => e.status === 'enrolled')
            .reduce((sum, e) => sum + e.credits, 0);

        this.statsEl.innerHTML = `
            <div class="stat-card"><div class="stat-label">Enrolled</div><div class="stat-value">${enrolled}</div></div>
            <div class="stat-card"><div class="stat-label">Waitlisted</div><div class="stat-value">${waitlisted}</div></div>
            <div class="stat-card"><div class="stat-label">Completed</div><div class="stat-value">${completed}</div></div>
            <div class="stat-card"><div class="stat-label">Current Credits</div><div class="stat-value">${credits}</div></div>
        `;
    },

    renderList(enrollments) {
        if (!enrollments.length) {
            this.listEl.innerHTML = `
                <div class="glass-card">
                    <div class="empty-state">
                        <p>No enrollments match your filters.</p>
                        <a href="/student/courses" class="btn btn-primary btn-sm" style="margin-top:0.75rem;">Course Registration</a>
                    </div>
                </div>`;
            return;
        }

        this.listEl.innerHTML = `
            <div class="glass-card">
                <div class="table-wrap">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Semester</th>
                                <th>Course</th>
                                <th>Credits</th>
                                <th>Instructor</th>
                                <th>Schedule</th>
                                <th>Grade</th>
                                <th>Status</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${enrollments.map((e) => this.enrollmentRow(e)).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        this.listEl.querySelectorAll('[data-drop-enrollment]').forEach((btn) => {
            btn.addEventListener('click', () => this.dropCourse(parseInt(btn.dataset.dropEnrollment), btn));
        });

    },

    enrollmentRow(enrollment) {
        const statusBadge = {
            enrolled: 'badge-enrolled',
            waitlisted: 'badge-amber',
            completed: 'badge-blue',
        }[enrollment.status] || 'badge-violet';

        const canDrop = ['enrolled', 'waitlisted'].includes(enrollment.status);
        const dropBtn = canDrop
            ? `<button class="btn btn-danger btn-sm" data-drop-enrollment="${enrollment.course_id}">Drop</button>`
            : '';

        return `
            <tr>
                <td>${enrollment.semester_name}</td>
                <td><strong>${enrollment.code}</strong><br><span style="color:var(--text-muted);font-size:0.8125rem;">${enrollment.title}</span></td>
                <td>${enrollment.credits_label || enrollment.credits}</td>
                <td>${enrollment.instructor_name || '—'}</td>
                <td>${enrollment.schedule_day || 'TBA'}<br><span style="font-size:0.8125rem;color:var(--text-muted);">${enrollment.schedule_time || ''}</span></td>
                <td>${enrollment.grade ? `<span class="badge badge-emerald">${enrollment.grade}</span>` : '—'}</td>
                <td><span class="badge ${statusBadge}">${enrollment.status}</span></td>
                <td>${dropBtn}</td>
            </tr>
        `;
    },

    async dropCourse(courseId, button) {
        if (!confirm('Drop this course? This cannot be undone for the current semester.')) return;

        UniERP.setButtonLoading(button, true);
        try {
            const data = await UniERP.apiFetch('/api/drop', {
                method: 'POST',
                body: JSON.stringify({ course_id: courseId }),
            });
            UniERP.showToast(data.message, 'success');
            await this.loadEnrollments();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        } finally {
            UniERP.setButtonLoading(button, false);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => StudentPortal.init());
