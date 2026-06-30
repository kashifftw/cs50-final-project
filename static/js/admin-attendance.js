const courseSelect = document.getElementById('course-select');
const panel = document.getElementById('attendance-panel');
const rosterEl = document.getElementById('attendance-roster');
const studentSelect = document.getElementById('att-student-select');

courseSelect?.addEventListener('change', async () => {
    const courseId = courseSelect.value;
    if (!courseId) {
        panel.style.display = 'none';
        return;
    }
    panel.style.display = 'block';
    rosterEl.innerHTML = '<p>Loading…</p>';
    const res = await fetch(`/api/admin/attendance/${courseId}`);
    const rows = await res.json();
    studentSelect.innerHTML = rows.map((r) =>
        `<option value="${r.enrollment_id}">${r.student_number} — ${r.first_name} ${r.last_name}</option>`
    ).join('');
    rosterEl.innerHTML = `
        <table class="data-table">
            <thead><tr><th>Student</th><th>Sessions</th><th>Present</th><th>%</th></tr></thead>
            <tbody>${rows.map((r) => `
                <tr>
                    <td>${r.student_number} — ${r.first_name} ${r.last_name}</td>
                    <td>${r.total_sessions}</td>
                    <td>${r.present}</td>
                    <td>${r.percentage}%</td>
                </tr>`).join('')}</tbody>
        </table>`;
});

document.getElementById('attendance-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const enrollmentId = studentSelect.value;
    const res = await fetch('/api/admin/attendance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            enrollment_id: enrollmentId,
            session_date: document.getElementById('att-date').value,
            status: document.getElementById('att-status').value,
        }),
    });
    const data = await res.json();
    alert(data.message);
    if (data.success) courseSelect.dispatchEvent(new Event('change'));
});
