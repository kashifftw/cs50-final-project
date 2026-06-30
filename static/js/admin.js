/**
 * UniERP — Registrar console (dynamic CRUD for catalog, semesters, settings).
 */

const AdminConsole = {
    departments: [],
    semesters: [],
    allCourses: [],

    init() {
        this.departments = JSON.parse(document.getElementById('registrar-data')?.dataset.departments || '[]');
        this.semesters = JSON.parse(document.getElementById('registrar-data')?.dataset.semesters || '[]');

        this.loadStats();
        this.loadCourses();
        this.loadDepartments();
        this.loadPrograms();
        this.loadSettings();

        document.getElementById('refresh-courses')?.addEventListener('click', () => this.loadCourses());
        document.getElementById('new-semester-form')?.addEventListener('submit', (e) => this.createSemester(e));
        document.getElementById('new-course-form')?.addEventListener('submit', (e) => this.createCourse(e));
        document.getElementById('new-department-form')?.addEventListener('submit', (e) => this.createDepartment(e));
        document.getElementById('new-program-form')?.addEventListener('submit', (e) => this.createProgram(e));
        document.getElementById('settings-form')?.addEventListener('submit', (e) => this.saveSettings(e));

        document.getElementById('semester-table')?.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-set-active], [data-toggle-reg], [data-edit-sem], [data-delete-sem]');
            if (!btn) return;
            if (btn.dataset.setActive) this.semesterAction('toggle_active', parseInt(btn.dataset.setActive));
            if (btn.dataset.toggleReg) this.semesterAction('toggle_registration', parseInt(btn.dataset.toggleReg));
            if (btn.dataset.editSem) this.editSemester(btn);
            if (btn.dataset.deleteSem) this.deleteSemester(parseInt(btn.dataset.deleteSem));
        });

        document.getElementById('edit-course-modal')?.addEventListener('submit', (e) => this.saveCourseEdit(e));
        document.getElementById('edit-course-cancel')?.addEventListener('click', () => this.hideEditModal());
    },

    async loadStats() {
        const grid = document.getElementById('admin-stats');
        if (!grid) return;
        try {
            const stats = await UniERP.apiFetch('/api/admin/stats');
            grid.querySelectorAll('[data-stat]').forEach((el) => {
                const key = el.dataset.stat;
                if (stats[key] !== undefined) el.textContent = stats[key];
            });
        } catch (_) { /* keep server-rendered values */ }
    },

    async semesterAction(action, semesterId) {
        try {
            const data = await UniERP.apiFetch('/api/admin/semesters', {
                method: 'POST',
                body: JSON.stringify({ action, semester_id: semesterId }),
            });
            UniERP.showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    editSemester(btn) {
        const name = prompt('Semester name:', btn.dataset.name);
        if (!name) return;
        const start = prompt('Start date (YYYY-MM-DD):', btn.dataset.start);
        if (!start) return;
        const end = prompt('End date (YYYY-MM-DD):', btn.dataset.end);
        if (!end) return;

        UniERP.apiFetch('/api/admin/semesters', {
            method: 'POST',
            body: JSON.stringify({
                action: 'update',
                semester_id: parseInt(btn.dataset.editSem),
                name: name.trim(),
                start_date: start.trim(),
                end_date: end.trim(),
            }),
        }).then((data) => {
            UniERP.showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        }).catch((err) => UniERP.showToast(err.message, 'error'));
    },

    async deleteSemester(semesterId) {
        if (!confirm('Delete this semester? It must have no courses.')) return;
        try {
            const data = await UniERP.apiFetch('/api/admin/semesters', {
                method: 'POST',
                body: JSON.stringify({ action: 'delete', semester_id: semesterId }),
            });
            UniERP.showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    async createSemester(e) {
        e.preventDefault();
        const form = e.target;
        try {
            const data = await UniERP.apiFetch('/api/admin/semesters', {
                method: 'POST',
                body: JSON.stringify({
                    name: form.name.value.trim(),
                    start_date: form.start_date.value,
                    end_date: form.end_date.value,
                }),
            });
            UniERP.showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    async createCourse(e) {
        e.preventDefault();
        const form = e.target;
        const payload = Object.fromEntries(new FormData(form));
        payload.prerequisite_ids = this.selectedPrereqIds('new-prerequisites');

        try {
            const data = await UniERP.apiFetch('/api/admin/courses', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            UniERP.showToast(data.message, 'success');
            form.reset();
            this.loadCourses();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    deptOptions(selectedId) {
        return this.departments.map((d) =>
            `<option value="${d.id}" ${String(d.id) === String(selectedId) ? 'selected' : ''}>${d.code}</option>`
        ).join('');
    },

    semOptions(selectedId) {
        return this.semesters.map((s) =>
            `<option value="${s.id}" ${String(s.id) === String(selectedId) ? 'selected' : ''}>${s.name}</option>`
        ).join('');
    },

    prereqOptions(courseId, selectedIds = []) {
        return this.allCourses
            .filter((c) => c.id !== courseId)
            .map((c) => {
                const selected = selectedIds.includes(c.id) ? 'selected' : '';
                return `<option value="${c.id}" ${selected}>${c.code} — ${c.title}</option>`;
            })
            .join('');
    },

    selectedPrereqIds(selectId) {
        const select = document.getElementById(selectId);
        if (!select) return [];
        return Array.from(select.selectedOptions).map((opt) => parseInt(opt.value, 10));
    },

    populatePrereqSelect(selectId, courseId = null, selectedIds = []) {
        const select = document.getElementById(selectId);
        if (!select) return;
        select.innerHTML = this.prereqOptions(courseId, selectedIds);
    },

    showEditModal(course) {
        const modal = document.getElementById('edit-course-modal');
        if (!modal) return;
        modal.dataset.courseId = course.id;
        modal.querySelector('[name="code"]').value = course.code;
        modal.querySelector('[name="title"]').value = course.title;
        modal.querySelector('[name="description"]').value = course.description || '';
        modal.querySelector('[name="has_lab"]').value = course.has_lab ? '1' : '0';
        modal.querySelector('[name="capacity"]').value = course.capacity;
        modal.querySelector('[name="schedule_day"]').value = course.schedule_day || '';
        modal.querySelector('[name="schedule_time"]').value = course.schedule_time || '';
        modal.querySelector('[name="room"]').value = course.room || '';
        modal.querySelector('[name="department_id"]').innerHTML = this.deptOptions(course.department_id);
        modal.querySelector('[name="semester_id"]').innerHTML = this.semOptions(course.semester_id);
        modal.querySelector('[name="instructor_name"]').value = course.instructor_name || '';
        this.populatePrereqSelect('edit-prerequisites', course.id, course.prerequisite_ids || []);
        modal.style.display = 'flex';
    },

    hideEditModal() {
        const modal = document.getElementById('edit-course-modal');
        if (modal) modal.style.display = 'none';
    },

    async saveCourseEdit(e) {
        e.preventDefault();
        const modal = document.getElementById('edit-course-modal');
        const courseId = modal.dataset.courseId;
        const form = e.target;
        const payload = Object.fromEntries(new FormData(form));
        payload.prerequisite_ids = this.selectedPrereqIds('edit-prerequisites');

        try {
            const data = await UniERP.apiFetch(`/api/admin/courses/${courseId}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
            UniERP.showToast(data.message, 'success');
            this.hideEditModal();
            this.loadCourses();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    async loadCourses() {
        const container = document.getElementById('admin-course-list');
        if (!container) return;

        container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span></div>';

        try {
            const courses = await UniERP.apiFetch('/api/admin/courses');
            this.allCourses = courses;
            this.populatePrereqSelect('new-prerequisites');
            if (!courses.length) {
                container.innerHTML = '<p class="empty-state">No courses in catalog.</p>';
                return;
            }

            container.innerHTML = `
                <div class="table-wrap">
                    <table class="data-table">
                        <thead>
                            <tr><th>Code</th><th>Title</th><th>Credits</th><th>Dept</th><th>Semester</th><th>Instructor</th><th>Cap.</th><th></th></tr>
                        </thead>
                        <tbody>
                            ${courses.map((c) => `
                                <tr>
                                    <td><strong>${c.code}</strong></td>
                                    <td>${c.title}</td>
                                    <td>${c.has_lab ? '3 (Theory + Lab)' : '2 (Theory)'}</td>
                                    <td>${c.department_code}</td>
                                    <td>${c.semester_name}</td>
                                    <td>${c.instructor_name || '—'}</td>
                                    <td>${c.capacity}</td>
                                    <td style="display:flex;gap:0.375rem;">
                                        <button class="btn btn-ghost btn-sm" data-edit-course='${JSON.stringify(c).replace(/'/g, '&#39;')}'>Edit</button>
                                        <button class="btn btn-danger btn-sm" data-delete-course="${c.id}">Delete</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;

            container.querySelectorAll('[data-delete-course]').forEach((btn) => {
                btn.addEventListener('click', () => this.deleteCourse(parseInt(btn.dataset.deleteCourse)));
            });
            container.querySelectorAll('[data-edit-course]').forEach((btn) => {
                btn.addEventListener('click', () => this.showEditModal(JSON.parse(btn.dataset.editCourse)));
            });
        } catch (err) {
            container.innerHTML = `<p class="empty-state">${err.message}</p>`;
        }
    },

    async deleteCourse(courseId) {
        if (!confirm('Delete this course? All enrollments will be removed.')) return;
        try {
            const data = await UniERP.apiFetch(`/api/admin/courses/${courseId}`, { method: 'DELETE' });
            UniERP.showToast(data.message, 'success');
            this.loadCourses();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    async loadDepartments() {
        const container = document.getElementById('department-list');
        if (!container) return;

        try {
            const departments = await UniERP.apiFetch('/api/admin/departments');
            this.departments = departments;
            if (!departments.length) {
                container.innerHTML = '<p class="empty-state">No departments yet.</p>';
                return;
            }

            container.innerHTML = `
                <div class="table-wrap">
                    <table class="data-table">
                        <thead><tr><th>Code</th><th>Name</th><th></th></tr></thead>
                        <tbody>
                            ${departments.map((d) => `
                                <tr>
                                    <td><strong>${d.code}</strong></td>
                                    <td>${d.name}</td>
                                    <td style="display:flex;gap:0.375rem;">
                                        <button class="btn btn-ghost btn-sm" data-edit-dept="${d.id}" data-code="${d.code}" data-name="${d.name}">Edit</button>
                                        <button class="btn btn-danger btn-sm" data-del-dept="${d.id}">Delete</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;

            container.querySelectorAll('[data-edit-dept]').forEach((btn) => {
                btn.addEventListener('click', () => this.editDepartment(btn));
            });
            container.querySelectorAll('[data-del-dept]').forEach((btn) => {
                btn.addEventListener('click', () => this.deleteDepartment(parseInt(btn.dataset.delDept)));
            });

            const progDept = document.getElementById('program_department_id');
            if (progDept) {
                progDept.innerHTML = '<option value="">— None —</option>' +
                    departments.map((d) => `<option value="${d.id}">${d.code} — ${d.name}</option>`).join('');
            }
        } catch (err) {
            container.innerHTML = `<p class="empty-state">${err.message}</p>`;
        }
    },

    async createDepartment(e) {
        e.preventDefault();
        const form = e.target;
        try {
            const data = await UniERP.apiFetch('/api/admin/departments', {
                method: 'POST',
                body: JSON.stringify({ code: form.code.value.trim(), name: form.name.value.trim() }),
            });
            UniERP.showToast(data.message, 'success');
            form.reset();
            this.loadDepartments();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    editDepartment(btn) {
        const code = prompt('Department code:', btn.dataset.code);
        if (!code) return;
        const name = prompt('Department name:', btn.dataset.name);
        if (!name) return;

        UniERP.apiFetch(`/api/admin/departments/${btn.dataset.editDept}`, {
            method: 'PUT',
            body: JSON.stringify({ code: code.trim(), name: name.trim() }),
        }).then((data) => {
            UniERP.showToast(data.message, 'success');
            this.loadDepartments();
        }).catch((err) => UniERP.showToast(err.message, 'error'));
    },

    async deleteDepartment(id) {
        if (!confirm('Delete this department?')) return;
        try {
            const data = await UniERP.apiFetch(`/api/admin/departments/${id}`, { method: 'DELETE' });
            UniERP.showToast(data.message, 'success');
            this.loadDepartments();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    async loadPrograms() {
        const container = document.getElementById('program-list');
        if (!container) return;

        try {
            const programs = await UniERP.apiFetch('/api/admin/programs?active_only=0');
            if (!programs.length) {
                container.innerHTML = '<p class="empty-state">No programs yet.</p>';
                return;
            }

            container.innerHTML = `
                <div class="table-wrap">
                    <table class="data-table">
                        <thead><tr><th>Program</th><th>Dept</th><th>Credits</th><th>Status</th><th></th></tr></thead>
                        <tbody>
                            ${programs.map((p) => `
                                <tr>
                                    <td><strong>${p.name}</strong></td>
                                    <td>${p.department_code || '—'}</td>
                                    <td>${p.credits_required}</td>
                                    <td>${p.is_active ? '<span class="badge badge-emerald">Active</span>' : '<span class="badge badge-red">Inactive</span>'}</td>
                                    <td style="display:flex;gap:0.375rem;">
                                        <button class="btn btn-ghost btn-sm" data-edit-prog='${JSON.stringify(p).replace(/'/g, '&#39;')}'>Edit</button>
                                        ${p.is_active ? `<button class="btn btn-danger btn-sm" data-del-prog="${p.id}">Deactivate</button>` : ''}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;

            container.querySelectorAll('[data-edit-prog]').forEach((btn) => {
                btn.addEventListener('click', () => this.editProgram(JSON.parse(btn.dataset.editProg)));
            });
            container.querySelectorAll('[data-del-prog]').forEach((btn) => {
                btn.addEventListener('click', () => this.deactivateProgram(parseInt(btn.dataset.delProg)));
            });
        } catch (err) {
            container.innerHTML = `<p class="empty-state">${err.message}</p>`;
        }
    },

    async createProgram(e) {
        e.preventDefault();
        const form = e.target;
        try {
            const data = await UniERP.apiFetch('/api/admin/programs', {
                method: 'POST',
                body: JSON.stringify({
                    name: form.name.value.trim(),
                    department_id: form.department_id.value || null,
                    credits_required: parseInt(form.credits_required.value, 10),
                }),
            });
            UniERP.showToast(data.message, 'success');
            form.reset();
            this.loadPrograms();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    editProgram(program) {
        const name = prompt('Program name:', program.name);
        if (!name) return;
        const credits = prompt('Credits required:', program.credits_required);
        if (!credits) return;
        const active = confirm('Keep program active? (Cancel to deactivate)');

        UniERP.apiFetch(`/api/admin/programs/${program.id}`, {
            method: 'PUT',
            body: JSON.stringify({
                name: name.trim(),
                department_id: program.department_id,
                credits_required: parseInt(credits, 10),
                is_active: active,
            }),
        }).then((data) => {
            UniERP.showToast(data.message, 'success');
            this.loadPrograms();
        }).catch((err) => UniERP.showToast(err.message, 'error'));
    },

    async deactivateProgram(id) {
        if (!confirm('Deactivate this program?')) return;
        try {
            const data = await UniERP.apiFetch(`/api/admin/programs/${id}`, { method: 'DELETE' });
            UniERP.showToast(data.message, 'success');
            this.loadPrograms();
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },

    async loadSettings() {
        const form = document.getElementById('settings-form');
        if (!form) return;

        try {
            const settings = await UniERP.apiFetch('/api/admin/settings');
            if (settings.portal_name) form.portal_name.value = settings.portal_name;
            if (settings.degree_credits_required) form.degree_credits_required.value = settings.degree_credits_required;
            if (settings.max_credit_hours_per_semester) form.max_credit_hours_per_semester.value = settings.max_credit_hours_per_semester;
            if (settings.registration_message) form.registration_message.value = settings.registration_message;
        } catch (_) { /* optional */ }
    },

    async saveSettings(e) {
        e.preventDefault();
        const form = e.target;
        try {
            const data = await UniERP.apiFetch('/api/admin/settings', {
                method: 'PUT',
                body: JSON.stringify({
                    portal_name: form.portal_name.value.trim(),
                    degree_credits_required: form.degree_credits_required.value,
                    max_credit_hours_per_semester: form.max_credit_hours_per_semester.value,
                    registration_message: form.registration_message.value.trim(),
                }),
            });
            UniERP.showToast(data.message, 'success');
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    },
};

document.addEventListener('DOMContentLoaded', () => AdminConsole.init());
