/**
 * UniERP — Authentication form validation (login).
 */

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const adminLoginForm = document.getElementById('admin-login-form');

    if (loginForm) {
        const rollNumber = document.getElementById('roll_number');
        const password = document.getElementById('password');

        const validateRollNumber = UniERP.bindValidation(rollNumber, (val) =>
            val.trim().length < 3 ? 'Roll number is required.' : null
        );
        const validatePassword = UniERP.bindValidation(password, (val) =>
            val.length < 1 ? 'Password is required.' : null
        );

        loginForm.addEventListener('submit', (e) => {
            const valid = validateRollNumber() & validatePassword();
            if (!valid) {
                e.preventDefault();
                return;
            }
            UniERP.setButtonLoading(loginForm.querySelector('[type="submit"]'), true);
        });
    }

    if (adminLoginForm) {
        const username = document.getElementById('username');
        const password = adminLoginForm.querySelector('#password');

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
