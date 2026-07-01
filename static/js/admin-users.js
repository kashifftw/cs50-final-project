/**
 * UniERP — Admin student enrollment (sessions, single add, bulk CSV, edit).
 */

document.addEventListener('DOMContentLoaded', () => {
    const addForm = document.getElementById('add-student-form');
    const bulkForm = document.getElementById('bulk-import-form');
    const sessionForm = document.getElementById('new-admission-session-form');
    const autoRoll = document.getElementById('auto_roll');
    const manualRollRow = document.getElementById('manual-roll-row');
    const sessionYear = document.getElementById('session_year');
    const bulkResults = document.getElementById('bulk-import-results');
    const editModal = document.getElementById('edit-student-modal');
    const editForm = document.getElementById('edit-student-form');
    let editingStudentId = null;

    if (sessionYear) {
        sessionYear.value = String(new Date().getFullYear());
    }

    refreshProgramDropdowns();

    const toggleManualRoll = () => {
        if (!autoRoll || !manualRollRow) return;
        const useAuto = autoRoll.checked;
        manualRollRow.style.display = useAuto ? 'none' : 'grid';
        document.getElementById('roll_number').required = !useAuto;
        document.getElementById('enrollment_year').required = !useAuto;
        document.getElementById('admission_session_id').required = useAuto;
    };

    autoRoll?.addEventListener('change', toggleManualRoll);
    toggleManualRoll();

    document.querySelectorAll('[data-toggle-session]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            try {
                const data = await UniERP.apiFetch('/api/admin/admission-sessions', {
                    method: 'POST',
                    body: JSON.stringify({ action: 'toggle_open', session_id: parseInt(btn.dataset.toggleSession, 10) }),
                });
                UniERP.showToast(data.message, 'success');
                setTimeout(() => location.reload(), 800);
            } catch (err) {
                UniERP.showToast(err.message, 'error');
            }
        });
    });

    document.querySelectorAll('[data-view-student]').forEach((btn) => {
        btn.addEventListener('click', () => viewStudentProfile(parseInt(btn.dataset.viewStudent, 10)));
    });

    document.querySelectorAll('[data-edit-student]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const student = JSON.parse(btn.dataset.editStudent);
            editingStudentId = student.id;
            editForm.roll_number.value = student.student_number || '';
            editForm.first_name.value = student.first_name || '';
            editForm.last_name.value = student.last_name || '';
            editForm.email.value = student.email || '';
            editForm.enrollment_year.value = student.enrollment_year || '';
            editForm.program.value = student.program || '';
            editForm.department_id.value = student.department_id || '';
            editForm.max_credit_hours.value = student.max_credit_hours ?? '';
            editForm.password.value = '';
            editModal.style.display = 'flex';
        });
    });

    document.querySelectorAll('[data-delete-student]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            if (!confirm('Remove this student account? This cannot be undone.')) return;
            try {
                const data = await UniERP.apiFetch(`/api/admin/students/${btn.dataset.deleteStudent}`, { method: 'DELETE' });
                UniERP.showToast(data.message, 'success');
                setTimeout(() => location.reload(), 800);
            } catch (err) {
                UniERP.showToast(err.message, 'error');
            }
        });
    });

    document.getElementById('edit-student-cancel')?.addEventListener('click', () => {
        editModal.style.display = 'none';
        editingStudentId = null;
    });

    editForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!editingStudentId) return;

        const payload = {
            roll_number: editForm.roll_number.value.trim(),
            first_name: editForm.first_name.value.trim(),
            last_name: editForm.last_name.value.trim(),
            email: editForm.email.value.trim(),
            program: editForm.program.value || null,
            enrollment_year: editForm.enrollment_year.value ? parseInt(editForm.enrollment_year.value, 10) : null,
            department_id: editForm.department_id.value ? parseInt(editForm.department_id.value, 10) : null,
            max_credit_hours: editForm.max_credit_hours.value ? parseInt(editForm.max_credit_hours.value, 10) : null,
        };
        if (editForm.password.value) payload.password = editForm.password.value;

        try {
            const data = await UniERP.apiFetch(`/api/admin/students/${editingStudentId}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
            UniERP.showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        } catch (err) {
            UniERP.showToast(err.message, 'error');
        }
    });

    sessionForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = sessionForm.querySelector('[type="submit"]');
        UniERP.setButtonLoading(submitBtn, true);
        try {
            const data = await UniERP.apiFetch('/api/admin/admission-sessions', {
                method: 'POST',
                body: JSON.stringify({
                    season: sessionForm.season.value,
                    year: parseInt(sessionForm.year.value, 10),
                }),
            });
            UniERP.showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        } catch (err) {
            UniERP.showToast(err.message, 'error');
            UniERP.setButtonLoading(submitBtn, false);
        }
    });

    addForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = addForm.querySelector('[type="submit"]');
        UniERP.setButtonLoading(submitBtn, true);

        const useAutoRoll = autoRoll.checked;
        const sessionId = addForm.admission_session_id.value;
        const departmentId = addForm.department_id.value;

        try {
            const payload = {
                auto_roll: useAutoRoll,
                admission_session_id: sessionId ? parseInt(sessionId, 10) : null,
                first_name: addForm.first_name.value.trim(),
                last_name: addForm.last_name.value.trim(),
                email: addForm.email.value.trim(),
                password: addForm.password.value,
                program: addForm.program.value.trim() || null,
                department_id: departmentId ? parseInt(departmentId, 10) : null,
            };

            if (!useAutoRoll) {
                payload.roll_number = addForm.roll_number.value.trim();
                payload.enrollment_year = parseInt(addForm.enrollment_year.value, 10);
            }

            const data = await UniERP.apiFetch('/api/admin/students', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            UniERP.showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        } catch (err) {
            UniERP.showToast(err.message, 'error');
            UniERP.setButtonLoading(submitBtn, false);
        }
    });

    bulkForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = bulkForm.querySelector('[type="submit"]');
        UniERP.setButtonLoading(submitBtn, true);
        bulkResults.style.display = 'none';
        bulkResults.innerHTML = '';

        const formData = new FormData();
        formData.append('admission_session_id', bulkForm.bulk_session_id.value);
        formData.append('default_password', bulkForm.bulk_password.value);
        formData.append('csv_file', bulkForm.csv_file.files[0]);

        try {
            const response = await fetch('/api/admin/students/bulk', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Import failed.');
            }

            UniERP.showToast(data.message, data.created_count ? 'success' : 'error');
            renderBulkResults(data);
            if (data.created_count) {
                setTimeout(() => location.reload(), 2000);
            } else {
                UniERP.setButtonLoading(submitBtn, false);
            }
        } catch (err) {
            UniERP.showToast(err.message, 'error');
            UniERP.setButtonLoading(submitBtn, false);
        }
    });

    document.getElementById('view-student-close')?.addEventListener('click', () => {
        document.getElementById('view-student-modal').style.display = 'none';
    });

    async function viewStudentProfile(studentId) {
        const modal = document.getElementById('view-student-modal');
        const content = document.getElementById('view-student-content');
        if (!modal || !content) return;

        modal.style.display = 'flex';
        content.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span></div>';

        try {
            const data = await UniERP.apiFetch(`/api/admin/students/${studentId}/profile`);
            const s = data.student;
            document.getElementById('view-student-title').textContent =
                `${s.first_name} ${s.last_name} (${s.student_number})`;

            const creditLine = data.credit_summary
                ? `${data.credit_summary.used}/${data.credit_summary.max} cr this semester`
                : '—';

            content.innerHTML = `
                <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(120px,1fr));margin-bottom:1rem;">
                    <div class="stat-card"><div class="stat-label">Credits</div><div class="stat-value">${creditLine}</div></div>
                    <div class="stat-card"><div class="stat-label">Fees Due</div><div class="stat-value">$${Number(data.fees.total_due || 0).toFixed(2)}</div></div>
                    <div class="stat-card"><div class="stat-label">Overdue</div><div class="stat-value">${data.fees.overdue_count || 0}</div></div>
                </div>
                <p style="font-size:0.875rem;color:var(--text-muted);margin-bottom:1rem;">
                    ${s.email} · ${s.program || 'Undeclared'}${s.department_code ? ` · ${s.department_code}` : ''}
                </p>

                <h3 style="font-size:0.9375rem;margin:1rem 0 0.5rem;">Enrolled Courses</h3>
                ${data.enrollments.length ? `
                <div class="table-wrap"><table class="data-table">
                    <thead><tr><th>Course</th><th>Semester</th><th>Credits</th><th>Status</th></tr></thead>
                    <tbody>
                        ${data.enrollments.map((e) => `
                            <tr>
                                <td><strong>${e.code}</strong><br><span style="font-size:0.75rem;color:var(--text-muted);">${e.title}</span></td>
                                <td>${e.semester_name}</td>
                                <td>${e.credits_label || e.credits}</td>
                                <td>${e.status}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table></div>` : '<p class="empty-state">No enrollments.</p>'}

                <h3 style="font-size:0.9375rem;margin:1rem 0 0.5rem;">Fee Status</h3>
                ${data.fees.fees?.length ? `
                <div class="table-wrap"><table class="data-table">
                    <thead><tr><th>Fee</th><th>Amount</th><th>Paid</th><th>Status</th></tr></thead>
                    <tbody>
                        ${data.fees.fees.map((f) => `
                            <tr>
                                <td>${f.description}</td>
                                <td>$${Number(f.amount).toFixed(2)}</td>
                                <td>$${Number(f.amount_paid).toFixed(2)}</td>
                                <td>${f.status}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table></div>` : '<p class="empty-state">No fee records.</p>'}
            `;
        } catch (err) {
            content.innerHTML = `<p class="empty-state">${err.message}</p>`;
        }
    }

    async function refreshProgramDropdowns() {
        try {
            const programs = await UniERP.apiFetch('/api/admin/programs');
            const names = programs.filter((p) => p.is_active).map((p) => p.name);
            ['program', 'edit-program-select'].forEach((id) => {
                const select = document.getElementById(id);
                if (!select) return;
                const current = select.value;
                select.innerHTML = '<option value="">— Select degree —</option>' +
                    names.map((n) => `<option value="${n}">${n}</option>`).join('');
                if (current) select.value = current;
            });
        } catch (_) { /* use server-rendered options */ }
    }

    function renderBulkResults(data) {
        bulkResults.style.display = 'block';
        let html = `<p><strong>${data.created_count}</strong> created, <strong>${data.failed_count}</strong> failed.</p>`;

        if (data.created?.length) {
            html += '<p style="margin-top:0.75rem;font-size:0.875rem;"><strong>Assigned roll numbers:</strong></p><ul style="font-size:0.8125rem;line-height:1.6;">';
            data.created.slice(0, 10).forEach((row) => {
                html += `<li>${row.roll_number} — ${row.name} (${row.email})</li>`;
            });
            if (data.created.length > 10) {
                html += `<li>…and ${data.created.length - 10} more</li>`;
            }
            html += '</ul>';
        }

        if (data.failed?.length) {
            html += '<p style="margin-top:0.75rem;font-size:0.875rem;color:var(--danger);"><strong>Failed rows:</strong></p><ul style="font-size:0.8125rem;line-height:1.6;">';
            data.failed.forEach((row) => {
                html += `<li>Row ${row.row}: ${row.name || '—'} — ${row.reason}</li>`;
            });
            html += '</ul>';
        }

        bulkResults.innerHTML = html;
    }
});
