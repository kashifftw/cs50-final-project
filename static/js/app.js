/**
 * UniERP — Shared frontend utilities (toasts, fetch helpers, validation, UX).
 */

const UniERP = {
    prefersReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    },

    /**
     * Display a transient toast notification.
     * @param {string} message - Text to display
     * @param {'success'|'error'|'info'} type - Visual variant
     */
    showToast(message, type = 'info') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            container.setAttribute('role', 'status');
            container.setAttribute('aria-live', 'polite');
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        const dismiss = () => {
            toast.classList.add('is-leaving');
            setTimeout(() => toast.remove(), 280);
        };

        setTimeout(dismiss, 4200);
        toast.addEventListener('click', dismiss);
    },

    /**
     * Perform an authenticated JSON fetch against the Flask API.
     * @param {string} url - Endpoint path
     * @param {object} options - fetch options
     * @returns {Promise<object>}
     */
    async apiFetch(url, options = {}) {
        const defaults = {
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
        };

        const response = await fetch(url, { ...defaults, ...options });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data.message || `Request failed (${response.status})`);
        }

        return data;
    },

    /**
     * Toggle loading state on a button during async work.
     * @param {HTMLButtonElement} button
     * @param {boolean} isLoading
     */
    setButtonLoading(button, isLoading) {
        if (!button) return;
        button.disabled = isLoading;
        button.classList.toggle('is-loading', isLoading);
        if (isLoading) {
            button.dataset.originalText = button.textContent;
        } else if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
        }
    },

    /**
     * Stagger animation on dynamically inserted elements.
     * @param {string|Element} container
     * @param {string} itemSelector
     */
    animateStagger(container, itemSelector) {
        const portal = document.documentElement.getAttribute('data-portal');
        if (portal === 'student' || portal === 'admin' || this.prefersReducedMotion()) return;

        const root = typeof container === 'string' ? document.querySelector(container) : container;
        if (!root) return;

        root.querySelectorAll(itemSelector).forEach((el, index) => {
            el.style.animationDelay = `${Math.min(index * 0.04, 0.32)}s`;
        });
    },

    /**
     * Animate progress bars from 0 to their target width.
     */
    initProgressBars() {
        const portal = document.documentElement.getAttribute('data-portal');
        const instant = portal === 'student' || portal === 'admin';

        document.querySelectorAll('.progress-fill[data-progress]').forEach((bar) => {
            const target = bar.dataset.progress;
            bar.style.setProperty('--progress-target', `${target}%`);

            if (instant || this.prefersReducedMotion()) {
                bar.classList.add('is-animated');
                return;
            }

            requestAnimationFrame(() => {
                requestAnimationFrame(() => bar.classList.add('is-animated'));
            });
        });
    },

    /**
     * Auto-dismiss flash alerts after a few seconds.
     */
    initFlashDismiss() {
        document.querySelectorAll('.flash-messages .alert').forEach((alert) => {
            setTimeout(() => {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-4px)';
                alert.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                setTimeout(() => alert.remove(), 320);
            }, 5000);
        });
    },

    /**
     * Attach real-time validation to a form field.
     */
    bindValidation(input, validator) {
        const errorEl = input.parentElement.querySelector('.form-error')
            || input.closest('.form-group')?.querySelector('.form-error');

        const validate = () => {
            const error = validator(input.value.trim());
            input.classList.toggle('invalid', !!error);
            input.classList.toggle('valid', !error && input.value.trim().length > 0);
            if (errorEl) errorEl.textContent = error || '';
            return !error;
        };

        input.addEventListener('input', validate);
        input.addEventListener('blur', validate);
        return validate;
    },

    initMobileNav() {
        const btn = document.getElementById('mobile-menu-btn');
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('sidebar-overlay');

        const closeSidebar = () => {
            sidebar?.classList.remove('open');
            overlay?.classList.remove('visible');
            overlay?.setAttribute('aria-hidden', 'true');
        };

        const openSidebar = () => {
            sidebar?.classList.add('open');
            overlay?.classList.add('visible');
            overlay?.setAttribute('aria-hidden', 'false');
        };

        btn?.addEventListener('click', () => {
            if (sidebar?.classList.contains('open')) closeSidebar();
            else openSidebar();
        });

        overlay?.addEventListener('click', closeSidebar);

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeSidebar();
                document.getElementById('notification-dropdown')?.classList.remove('open');
                UniERP.closeProfileMenu();
            }
        });
    },

    isNotificationUnread(notification) {
        return Number(notification.is_read) === 0;
    },

    updateNotificationBadge(count) {
        const bell = document.getElementById('notification-bell');
        if (!bell) return;

        const unread = Math.max(0, Number(count) || 0);
        let badge = bell.querySelector('.notification-badge');

        if (unread <= 0) {
            badge?.remove();
            return;
        }

        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'notification-badge';
            bell.appendChild(badge);
        }

        badge.textContent = String(unread);
    },

    async markAllNotificationsRead() {
        const data = await this.apiFetch('/api/notifications/read', {
            method: 'POST',
            body: JSON.stringify({}),
        });
        this.updateNotificationBadge(data.unread_count ?? 0);
        return data;
    },

    async markNotificationRead(notificationId) {
        const data = await this.apiFetch('/api/notifications/read', {
            method: 'POST',
            body: JSON.stringify({ notification_id: notificationId }),
        });
        this.updateNotificationBadge(data.unread_count ?? 0);
        return data;
    },

    async loadNotifications(markAllRead = false) {
        const panel = document.getElementById('notification-panel');
        if (!panel) return;

        panel.innerHTML = '<div class="loading-overlay" style="padding:1rem;"><span class="loading-spinner"></span></div>';

        try {
            if (markAllRead) {
                await this.markAllNotificationsRead();
            }

            const notifications = await this.apiFetch('/api/notifications');
            const unreadCount = notifications.filter((n) => this.isNotificationUnread(n)).length;
            this.updateNotificationBadge(unreadCount);

            if (notifications.length === 0) {
                panel.innerHTML = '<p class="empty-state" style="padding:1rem;">No notifications</p>';
                return;
            }

            panel.innerHTML = `<ul class="notification-list">${notifications.map(n => `
                <li class="notification-item ${this.isNotificationUnread(n) ? 'unread' : ''}" data-id="${n.id}" role="button" tabindex="0">
                    ${n.link ? `<a href="${n.link}" class="notification-link">${n.message}</a>` : `<span class="notification-message">${n.message}</span>`}
                    <div class="notification-time">${n.created_at}</div>
                </li>
            `).join('')}</ul>`;

            const handleMarkRead = async (item) => {
                const id = parseInt(item.dataset.id, 10);
                const link = item.querySelector('.notification-link')?.getAttribute('href');

                if (item.classList.contains('unread')) {
                    try {
                        await this.markNotificationRead(id);
                        item.classList.remove('unread');
                    } catch (err) {
                        this.showToast(err.message, 'error');
                        return;
                    }
                }

                if (link) {
                    window.location.href = link;
                    return;
                }

                await this.loadNotifications();
            };

            panel.querySelectorAll('.notification-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    handleMarkRead(item);
                });
                item.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleMarkRead(item);
                    }
                });
            });
        } catch (err) {
            panel.innerHTML = `<p class="empty-state" style="padding:1rem;">${err.message}</p>`;
        }
    },

    initNotificationBell() {
        const bell = document.getElementById('notification-bell');
        const dropdown = document.getElementById('notification-dropdown');
        if (!bell || !dropdown) return;

        bell.addEventListener('click', async (e) => {
            e.stopPropagation();
            this.closeProfileMenu();
            const isOpening = !dropdown.classList.contains('open');
            dropdown.classList.toggle('open');
            if (isOpening) {
                await this.loadNotifications(true);
            }
        });

        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target) && !bell.contains(e.target)) {
                dropdown.classList.remove('open');
            }
        });
    },

    initProfileMenu() {
        const menu = document.getElementById('portal-profile-menu');
        const btn = document.getElementById('profile-menu-btn');
        if (!menu || !btn) return;

        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            document.getElementById('notification-dropdown')?.classList.remove('open');
            const isOpen = menu.classList.toggle('is-open');
            btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });

        document.addEventListener('click', (e) => {
            if (!menu.contains(e.target)) {
                this.closeProfileMenu();
            }
        });
    },

    closeProfileMenu() {
        const menu = document.getElementById('portal-profile-menu');
        const btn = document.getElementById('profile-menu-btn');
        if (!menu) return;
        menu.classList.remove('is-open');
        btn?.setAttribute('aria-expanded', 'false');
    },

    initTabs(containerSelector) {
        const container = document.querySelector(containerSelector);
        if (!container) return;

        const tabs = container.querySelectorAll('.tab-btn');
        const panels = container.querySelectorAll('.tab-panel');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                panels.forEach(p => {
                    p.classList.remove('active');
                    p.style.animation = 'none';
                });
                tab.classList.add('active');
                const panel = container.querySelector(`#${tab.dataset.tab}`);
                if (panel) {
                    panel.classList.add('active');
                    if (!this.prefersReducedMotion()) {
                        void panel.offsetWidth;
                        panel.style.animation = '';
                    }
                }
            });
        });
    },

    openModal(id) {
        document.getElementById(id)?.classList.add('open');
    },

    closeModal(id) {
        document.getElementById(id)?.classList.remove('open');
    },

    initModals() {
        document.querySelectorAll('[data-modal-close]').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.closest('.modal-backdrop')?.classList.remove('open');
            });
        });

        document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
            backdrop.addEventListener('click', (e) => {
                if (e.target === backdrop) backdrop.classList.remove('open');
            });
        });
    },

    initPageUX() {
        this.initProgressBars();
        this.initFlashDismiss();
    },

    getTheme() {
        return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    },

    applyTheme(theme) {
        const isDark = theme === 'dark';
        if (isDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        localStorage.setItem('theme', theme);
        document.querySelectorAll('.theme-toggle').forEach((btn) => {
            btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
            btn.setAttribute('title', isDark ? 'Light mode' : 'Dark mode');
        });
    },

    initTheme() {
        const saved = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = saved || (prefersDark ? 'dark' : 'light');
        this.applyTheme(theme);

        document.querySelectorAll('.theme-toggle').forEach((btn) => {
            btn.addEventListener('click', () => {
                this.applyTheme(this.getTheme() === 'dark' ? 'light' : 'dark');
            });
        });
    },
};

document.addEventListener('DOMContentLoaded', () => {
    UniERP.initTheme();
    UniERP.initMobileNav();
    UniERP.initNotificationBell();
    UniERP.initProfileMenu();
    UniERP.initModals();
    UniERP.initPageUX();
});
