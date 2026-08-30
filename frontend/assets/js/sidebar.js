/* ============================================================
   IHMIS — sidebar.js
   Handles: sidebar toggle (collapse/expand), mobile overlay,
   active nav link highlighting, user dropdown menu.
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  const layout       = document.querySelector('.app-layout');
  const toggleBtn    = document.getElementById('sidebarToggle');
  const overlay      = document.querySelector('.sidebar-overlay');
  const userMenuBtn  = document.getElementById('userMenuBtn');
  const userDropdown = document.getElementById('userDropdown');

  /* ── 1. Sidebar Toggle (desktop collapse / mobile open) ─── */
  if (toggleBtn && layout) {
    toggleBtn.addEventListener('click', () => {
      const isMobile = window.innerWidth <= 768;

      if (isMobile) {
        layout.classList.toggle('mobile-open');
      } else {
        layout.classList.toggle('sidebar-collapsed');
        // Save preference
        const collapsed = layout.classList.contains('sidebar-collapsed');
        localStorage.setItem('ihmis_sidebar_collapsed', collapsed);
      }
    });
  }

  /* Restore collapsed state on desktop */
  if (layout && window.innerWidth > 768) {
    const wasCollapsed = localStorage.getItem('ihmis_sidebar_collapsed') === 'true';
    if (wasCollapsed) layout.classList.add('sidebar-collapsed');
  }

  /* ── 2. Mobile overlay click closes sidebar ─────────────── */
  if (overlay && layout) {
    overlay.addEventListener('click', () => {
      layout.classList.remove('mobile-open');
    });
  }

  /* ── 3. Active nav link ──────────────────────────────────── */
  const currentPath = window.location.pathname.split('/').pop();
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href && href.includes(currentPath) && currentPath !== '') {
      link.classList.add('active');
    }
  });

  /* ── 4. User dropdown menu ───────────────────────────────── */
  if (userMenuBtn && userDropdown) {
    userMenuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      userDropdown.classList.toggle('open');
    });

    // Close on outside click only — closing on every click (including
    // clicks on the dropdown's own items) was hiding the dropdown in the
    // same tick as a link inside it was clicked, which silently cancelled
    // the link's navigation (a known browser quirk: hiding an element
    // during its own click event can cancel the pending default action).
    // That's why "My Profile" intermittently did nothing.
    document.addEventListener('click', (e) => {
      if (!userDropdown.contains(e.target) && !userMenuBtn.contains(e.target)) {
        userDropdown.classList.remove('open');
      }
    });
  }

  /* ── 5. Logout button ────────────────────────────────────── */
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      clearSession();
      window.location.href = '../../index.html';
    });
  }

  /* ── 6. Fill in user info from localStorage ──────────────── */
  const user = getUser();
  if (user) {
    const initials = getInitials(user.full_name || user.username || 'U');

    // Sidebar avatar + name
    const sidebarAvatar = document.getElementById('sidebarAvatar');
    const sidebarName   = document.getElementById('sidebarName');
    const sidebarRole   = document.getElementById('sidebarRole');
    if (sidebarAvatar) sidebarAvatar.textContent = initials;
    if (sidebarName)   sidebarName.textContent   = user.full_name || user.username;
    if (sidebarRole)   sidebarRole.textContent   = formatRole(user.role);

    // Navbar avatar + name
    const navbarAvatar = document.getElementById('navbarAvatar');
    const navbarName   = document.getElementById('navbarName');
    if (navbarAvatar) navbarAvatar.textContent = initials;
    if (navbarName)   navbarName.textContent   = user.full_name || user.username;

    // Dropdown header
    const dropdownName = document.getElementById('dropdownName');
    const dropdownRole = document.getElementById('dropdownRole');
    if (dropdownName) dropdownName.textContent = user.full_name || user.username;
    if (dropdownRole) dropdownRole.textContent = formatRole(user.role);

    // ── 6b. Doctor/Nurse on-duty toggle ──────────────────────────
    // Injected here (shared across every page) rather than duplicated
    // in each doctor/*.html or nurse/*.html file, so it appears
    // consistently on every page of both portals with a single source
    // of truth. Only renders for the Doctor or Nurse role -- everyone
    // else's navbar is untouched. This is what drives the Nurse's
    // on-duty doctor picker on Forward to Doctor, and the MHO's
    // on-duty nurse picker on Forward to Nurse.
    const isDoctor = user.role === 'doctor' ||
                      (Array.isArray(user.roles) && user.roles.some(r => String(r).toLowerCase() === 'doctor'));
    const isNurse  = user.role === 'nurse' ||
                      (Array.isArray(user.roles) && user.roles.some(r => String(r).toLowerCase() === 'nurse'));
    const navbarRight = document.querySelector('.navbar-right');
    if ((isDoctor || isNurse) && navbarRight && !document.getElementById('dutyToggleWrap')) {
      renderDutyToggle(navbarRight, !!user.is_on_duty);
    }
  }

});

/* ── Doctor/Nurse on-duty toggle ─────────────────────────────── */
function renderDutyToggle(navbarRight, initialOnDuty) {
  const wrap = document.createElement('div');
  wrap.id = 'dutyToggleWrap';
  wrap.style.cssText = 'display:flex;align-items:center;gap:0.5rem;margin-right:0.75rem;padding:0.3rem 0.7rem;border-radius:999px;border:1px solid var(--border-light)';
  wrap.innerHTML = `
    <span id="dutyToggleLabel" style="font-size:0.78rem;font-weight:600;white-space:nowrap;color:${initialOnDuty ? 'var(--success, #16a34a)' : 'var(--text-muted)'}">
      ${initialOnDuty ? 'On Duty' : 'Off Duty'}
    </span>
    <label style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer;flex-shrink:0">
      <input type="checkbox" id="dutyToggleInput" ${initialOnDuty ? 'checked' : ''} style="opacity:0;width:0;height:0">
      <span id="dutyToggleTrack" style="position:absolute;inset:0;background:${initialOnDuty ? 'var(--success, #16a34a)' : '#cbd5e1'};border-radius:999px;transition:background 0.15s">
        <span id="dutyToggleKnob" style="position:absolute;top:2px;left:${initialOnDuty ? '18px' : '2px'};width:16px;height:16px;background:#fff;border-radius:50%;transition:left 0.15s;box-shadow:0 1px 2px rgba(0,0,0,0.25)"></span>
      </span>
    </label>
  `;
  navbarRight.insertBefore(wrap, navbarRight.firstChild);

  const input = wrap.querySelector('#dutyToggleInput');
  const track = wrap.querySelector('#dutyToggleTrack');
  const knob  = wrap.querySelector('#dutyToggleKnob');
  const label = wrap.querySelector('#dutyToggleLabel');

  input.addEventListener('change', async () => {
    const goingOnDuty = input.checked;
    input.disabled = true;

    try {
      const res = await api.patch('/auth/me/duty-status', { is_on_duty: goingOnDuty });
      const updatedUser = res.data;

      // Keep sessionStorage in sync so a page refresh (or navigating to
      // another doctor page) shows the correct state immediately, without
      // waiting on a fresh /auth/me call.
      const stored = getUser();
      if (stored) {
        stored.is_on_duty = updatedUser.is_on_duty;
        sessionStorage.setItem('ihmis_user', JSON.stringify(stored));
      }

      track.style.background = goingOnDuty ? 'var(--success, #16a34a)' : '#cbd5e1';
      knob.style.left         = goingOnDuty ? '18px' : '2px';
      label.textContent       = goingOnDuty ? 'On Duty' : 'Off Duty';
      label.style.color       = goingOnDuty ? 'var(--success, #16a34a)' : 'var(--text-muted)';

      if (typeof showToast === 'function') {
        showToast(goingOnDuty ? 'You are now on duty.' : 'You are now off duty.', 'success');
      }
    } catch (err) {
      // Revert the checkbox -- the request failed, so the toggle should
      // visually snap back rather than show a state that never actually
      // took effect server-side.
      input.checked = !goingOnDuty;
      if (typeof showToast === 'function') {
        showToast(err.message || 'Could not update duty status.', 'error');
      }
    } finally {
      input.disabled = false;
    }
  });
}

/* ── Helpers ─────────────────────────────────────────────────*/
function getInitials(name) {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function formatRole(role) {
  const map = {
    admin:      'Administrator',
    doctor:     'Doctor',
    pharmacist: 'Pharmacist',
    lab_tech:   'Lab Technician',
    nurse:      'Nurse',
    mho:        'Medical Health Officer',
  };
  return map[role] || role;
}