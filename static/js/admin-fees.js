document.getElementById('fee-item-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    if (!payload.semester_id) delete payload.semester_id;
    const res = await fetch('/api/admin/fee-items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    alert(data.message);
    if (data.success) location.reload();
});

document.getElementById('assign-fee-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    const res = await fetch('/api/admin/student-fees', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    alert(data.message);
    if (data.success) e.target.reset();
});
