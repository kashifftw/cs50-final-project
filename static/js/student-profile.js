document.getElementById('profile-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const msg = document.getElementById('profile-message');
    const btn = document.getElementById('profile-save-btn');
    btn.disabled = true;
    msg.textContent = 'Saving…';

    const body = new FormData(form);
    try {
        const res = await fetch('/api/student/profile', { method: 'PUT', body });
        const data = await res.json();
        msg.textContent = data.message || (data.success ? 'Saved.' : 'Error.');
        msg.style.color = data.success ? 'var(--success)' : 'var(--danger)';
        if (data.success && data.profile_picture) {
            setTimeout(() => window.location.reload(), 800);
        }
    } catch {
        msg.textContent = 'Network error.';
    }
    btn.disabled = false;
});
