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

    // Close on outside click
    document.addEventListener('click', () => {
      userDropdown.classList.remove('open');
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
  }

});

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