document.addEventListener('DOMContentLoaded', () => {

  if (isLoggedIn()) {
    const existingUser = getUser();
    if (existingUser && existingUser.role) {
      redirectByRole(existingUser.role);
      return;
    }
    // Token exists but user/role data is missing or invalid — clear it
    // so we fall through to showing the login form instead of silently
    // leaving the submit handler unattached.
    clearSession();
  }

  const loginForm     = document.getElementById('loginForm');
  const roleSelect     = document.getElementById('role');
  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');
  const loginBtn      = document.getElementById('loginBtn');
  const loginBtnText  = document.getElementById('loginBtnText');
  const spinner       = document.getElementById('loginSpinner');
  const errorBox      = document.getElementById('loginError');
  const togglePwd     = document.getElementById('togglePassword');

  // Human-readable labels for the error message when the selected role
  // doesn't match the account's actual role. Keys must match the
  // <option value="..."> values in index.html, which already match the
  // mapped output of roleMap below (admin, mho, nurse, doctor, lab_tech,
  // pharmacist) — so no extra translation layer is needed.
  const roleLabels = {
    admin:      'Admin',
    mho:        'Medical Health Officer',
    nurse:      'Nurse',
    doctor:     'Doctor',
    lab_tech:   'Laboratory Technician',
    pharmacist: 'Pharmacist',
  };

  if (togglePwd) {
    togglePwd.addEventListener('click', () => {
      const isText = passwordInput.type === 'text';
      passwordInput.type = isText ? 'password' : 'text';
      togglePwd.innerHTML = isText
        ? '<i class="fa-solid fa-eye"></i>'
        : '<i class="fa-solid fa-eye-slash"></i>';
    });
  }

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const selectedRole = roleSelect.value;
    const username      = usernameInput.value.trim();
    const password      = passwordInput.value.trim();

    if (!selectedRole) {
      showError('Please select the role you are signing in as.');
      return;
    }

    if (!username || !password) {
      showError('Please enter your username and password.');
      return;
    }

    setLoading(true);

    try {
      const response = await api.post('/auth/login', { username, password, role: selectedRole });
      console.log('Full response:', response);

      // Backend wraps the payload in a "data" field:
      // { data: { access_token, user }, message, success }
      const { access_token, user } = response.data;

      if (!access_token || !user) {
        throw new Error('Unexpected response from server. Check the console log above.');
      }

      console.log('User object:', user);
      console.log('Roles:', user.roles);

      // Backend returns roles as array e.g. ["Admin"]
      const roleRaw = Array.isArray(user.roles) ? user.roles[0] : user.roles;
      console.log('Role raw:', roleRaw);

      if (!roleRaw) {
        showError('No role assigned to this user. Contact an administrator.');
        return;
      }

      // IMPORTANT: every role string returned by the backend (see
      // app/utils/constants.py Roles class) MUST have an entry here.
      // A missing entry silently falls through to .toLowerCase(), which
      // produces a key like "medical health officer" (with spaces) that
      // won't match anything in api.js's redirectByRole() routes or
      // sidebar.js's formatRole() map — causing a redirect loop back to
      // login. This is what caused the MHO infinite-spinner bug.
      const roleMap = {
        'Admin':                   'admin',
        'Doctor':                  'doctor',
        'Pharmacist':              'pharmacist',
        'Lab_Tech':                'lab_tech',
        'Lab Technician':          'lab_tech',
        'Nurse':                   'nurse',
        'Medical Health Officer':  'mho',
      };

      user.role = roleMap[roleRaw] || roleRaw.toLowerCase();
      console.log('Mapped role:', user.role);

      // Guard against picking the wrong role in the dropdown — e.g. a
      // Nurse account selecting "Doctor". The credentials are valid, but
      // this isn't the account/role combination the user asked to sign
      // in as, so we stop before saving a session or redirecting.
      if (user.role !== selectedRole) {
        const actualLabel = roleLabels[user.role] || roleRaw;
        showError(`This account is registered as ${actualLabel}, not ${roleLabels[selectedRole]}. Please select the correct role.`);
        return;
      }

      saveSession(access_token, user);
      console.log('Session saved. Redirecting to:', user.role);

      redirectByRole(user.role);

    } catch (error) {
      console.error('Login error:', error);
      showError(error.message || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  });

  function setLoading(state) {
    loginBtn.disabled        = state;
    spinner.style.display    = state ? 'inline-block' : 'none';
    loginBtnText.textContent = state ? 'Signing in...' : 'Sign In';
  }

  function showError(message) {
    errorBox.querySelector('span').textContent = message;
    errorBox.style.display = 'flex';
  }

  function clearError() {
    errorBox.style.display = 'none';
  }

});