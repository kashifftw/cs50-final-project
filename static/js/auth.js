/**
 * UniERP — Authentication form validation (login).
 */

document.addEventListener('DOMContentLoaded', () => {
    initAuthPortalSwitchEnter();
    initAuthPageTransitions();

    const loginForm = document.getElementById('login-form');
    const adminLoginForm = document.getElementById('admin-login-form');

    if (loginForm) {
        const sessionSeasonInputs = loginForm.querySelectorAll('input[name="session_season"]');
        const sessionYear = document.getElementById('session_year');
        const departmentCode = document.getElementById('department_code');
        const rollSequence = document.getElementById('roll_sequence');
        const password = document.getElementById('student_password');
        const patternError = document.getElementById('login-pattern-error');
        const idPreview = document.getElementById('login-id-preview');
        const idPreviewValue = document.getElementById('login-id-preview-value');

        const YEAR_RE = /^\d{2}$/;
        const ROLL_RE = /^\d{1,4}$/;

        const getSelectedSeason = () => {
            const checked = loginForm.querySelector('input[name="session_season"]:checked');
            return checked ? checked.value : '';
        };

        const updateIdPreview = () => {
            const seasonVal = getSelectedSeason();
            const yearVal = (sessionYear?.value || '').trim();
            const degreeVal = (departmentCode?.value || '').trim();
            const rollVal = (rollSequence?.value || '').trim();

            const sessionPart = seasonVal && YEAR_RE.test(yearVal) ? `${seasonVal}${yearVal}` : '—';
            const degreePart = degreeVal || '—';
            const rollPart = rollVal || '—';

            if (idPreviewValue) {
                idPreviewValue.textContent = `${sessionPart} · ${degreePart} · ${rollPart}`;
            }

            const isComplete = Boolean(
                seasonVal
                && YEAR_RE.test(yearVal)
                && degreeVal
                && ROLL_RE.test(rollVal)
            );
            idPreview?.classList.toggle('is-complete', isComplete);
        };

        const validateLoginPattern = () => {
            const seasonVal = getSelectedSeason();
            const yearVal = (sessionYear?.value || '').trim();
            const degreeVal = (departmentCode?.value || '').trim();
            const rollVal = (rollSequence?.value || '').trim();

            if (!seasonVal) {
                return 'Choose Fall or Spring for your admission session.';
            }
            if (!YEAR_RE.test(yearVal)) {
                return 'Enter the last two digits of your batch year (e.g. 24).';
            }
            if (!degreeVal) {
                return 'Choose your degree program.';
            }
            if (!ROLL_RE.test(rollVal)) {
                return 'Roll number must be 1–4 digits only.';
            }
            return null;
        };

        sessionYear?.addEventListener('input', () => {
            sessionYear.value = sessionYear.value.replace(/\D/g, '').slice(0, 2);
            updateIdPreview();
        });

        sessionSeasonInputs.forEach((input) => {
            input.addEventListener('change', updateIdPreview);
        });
        departmentCode?.addEventListener('change', updateIdPreview);
        rollSequence?.addEventListener('input', updateIdPreview);

        updateIdPreview();
        initStudentLoginAutofillGuard(loginForm, {
            sessionYear,
            rollSequence,
            password,
            departmentCode,
            sessionSeasonInputs,
            updateIdPreview,
        });

        const validatePassword = UniERP.bindValidation(password, (val) =>
            val.length < 1 ? 'Password is required.' : null
        );

        loginForm.addEventListener('submit', (e) => {
            const patternMessage = validateLoginPattern();
            if (patternError) {
                patternError.textContent = patternMessage || '';
            }
            const valid = !patternMessage && validatePassword();
            if (!valid) {
                e.preventDefault();
                if (patternMessage) {
                    if (!getSelectedSeason() && sessionSeasonInputs[0]) {
                        sessionSeasonInputs[0].focus();
                    } else if (!YEAR_RE.test((sessionYear?.value || '').trim()) && sessionYear) {
                        sessionYear.focus();
                    } else if (!departmentCode?.value && departmentCode) {
                        departmentCode.focus();
                    } else if (rollSequence) {
                        rollSequence.focus();
                    }
                }
                return;
            }
            UniERP.setButtonLoading(loginForm.querySelector('[type="submit"]'), true);
        });
    }

    if (adminLoginForm) {
        const username = document.getElementById('admin_username');
        const password = document.getElementById('admin_password');

        const validateUsername = UniERP.bindValidation(username, (val) =>
            val.length < 1 ? 'Username is required.' : null
        );
        const validatePassword = UniERP.bindValidation(password, (val) =>
            val.length < 1 ? 'Password is required.' : null
        );

        adminLoginForm.addEventListener('submit', (e) => {
            const valid = validateUsername() & validatePassword();
            if (!valid) {
                e.preventDefault();
                return;
            }
            UniERP.setButtonLoading(adminLoginForm.querySelector('[type="submit"]'), true);
        });
    }
});

/**
 * Prevent browser password managers from filling admin credentials into student login.
 */
function initStudentLoginAutofillGuard(form, fields) {
    const {
        sessionYear,
        rollSequence,
        password,
        departmentCode,
        sessionSeasonInputs,
        updateIdPreview,
    } = fields;

    const params = new URLSearchParams(window.location.search);
    const loggedOut = params.get('logged_out') === '1';

    const clearAutofilledValues = () => {
        const hasServerSessionYear = Boolean(sessionYear?.defaultValue);
        const hasServerRoll = Boolean(rollSequence?.defaultValue);
        const hasServerDegree = Boolean(
            departmentCode?.querySelector('option[selected]:not([value=""])')
        );

        if (!hasServerSessionYear && sessionYear) {
            sessionYear.value = '';
        }
        if (!hasServerRoll && rollSequence) {
            rollSequence.value = '';
        }
        if (!hasServerDegree && departmentCode) {
            departmentCode.selectedIndex = 0;
        }
        if (password) {
            password.value = '';
        }
        sessionSeasonInputs?.forEach((input) => {
            if (!input.defaultChecked) {
                input.checked = false;
            }
        });
        updateIdPreview?.();
    };

    if (loggedOut) {
        clearAutofilledValues();
        window.setTimeout(clearAutofilledValues, 50);
        window.setTimeout(clearAutofilledValues, 250);
    }

    form.querySelectorAll('.form-input, .auth-year-field').forEach((input) => {
        if (input.value) {
            return;
        }
        input.setAttribute('readonly', 'readonly');
        input.addEventListener('focus', () => {
            input.removeAttribute('readonly');
        }, { once: true });
    });
}

const AUTH_SWITCH_KEY = 'authPortalSwitch';
const AUTH_SWITCH_MS = 500;

/**
 * Fade-in when arriving from a student ↔ admin login switch.
 */
function initAuthPortalSwitchEnter() {
    if (sessionStorage.getItem(AUTH_SWITCH_KEY) !== '1') return;

    sessionStorage.removeItem(AUTH_SWITCH_KEY);

    if (typeof UniERP !== 'undefined' && UniERP.prefersReducedMotion && UniERP.prefersReducedMotion()) {
        document.documentElement.classList.remove('auth-is-entering');
        return;
    }

    if (!document.documentElement.classList.contains('auth-is-entering')) {
        document.documentElement.classList.add('auth-is-entering');
    }

    const shell = document.querySelector('.auth-shell');
    const cleanup = () => document.documentElement.classList.remove('auth-is-entering');

    if (shell) {
        shell.addEventListener('animationend', (event) => {
            if (event.animationName === 'motion-auth-enter') cleanup();
        }, { once: true });
    }

    window.setTimeout(cleanup, AUTH_SWITCH_MS + 50);
}

/**
 * Smooth fade-out before navigating between student and admin login pages.
 */
function initAuthPageTransitions() {
    document.querySelectorAll('.auth-page-transition').forEach((link) => {
        link.addEventListener('click', (e) => {
            const href = link.getAttribute('href');
            if (!href || link.target === '_blank') return;

            if (typeof UniERP !== 'undefined' && UniERP.prefersReducedMotion && UniERP.prefersReducedMotion()) {
                return;
            }

            e.preventDefault();
            sessionStorage.setItem(AUTH_SWITCH_KEY, '1');

            const shell = document.querySelector('.auth-shell');
            document.documentElement.classList.add('auth-is-leaving');

            if (shell) {
                void shell.offsetHeight;
            }

            let navigated = false;
            const navigate = () => {
                if (navigated) return;
                navigated = true;
                window.location.href = href;
            };

            if (shell) {
                shell.addEventListener('transitionend', (event) => {
                    if (event.propertyName === 'opacity') navigate();
                }, { once: true });
            }

            window.setTimeout(navigate, AUTH_SWITCH_MS + 80);
        });
    });
}
