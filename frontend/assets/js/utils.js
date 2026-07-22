/* ============================================================
   IHMIS — utils.js
   Shared helper functions used across all pages.
   ============================================================ */

/* ── Toast Notifications ─────────────────────────────────────*/
function showToast(message, type = 'success', duration = 3500) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = `
      position: fixed; bottom: 1.5rem; right: 1.5rem;
      display: flex; flex-direction: column; gap: 0.5rem;
      z-index: 9999; pointer-events: none;
    `;
    document.body.appendChild(container);
  }

  const icons = {
    success: 'fa-circle-check',
    error:   'fa-circle-exclamation',
    warning: 'fa-triangle-exclamation',
    info:    'fa-circle-info',
  };

  const colors = {
    success: '#00b894',
    error:   '#e17055',
    warning: '#fdcb6e',
    info:    '#0984e3',
  };

  const toast = document.createElement('div');
  toast.style.cssText = `
    display: flex; align-items: center; gap: 0.6rem;
    background: #fff; border-left: 4px solid ${colors[type]};
    padding: 0.8rem 1.1rem; border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.12);
    font-size: 0.875rem; color: #2d3436;
    pointer-events: all; min-width: 260px;
    animation: slideIn 0.3s ease;
    font-family: 'Inter', sans-serif;
  `;

  toast.innerHTML = `
    <i class="fa-solid ${icons[type]}" style="color:${colors[type]};font-size:1rem;"></i>
    <span style="flex:1">${message}</span>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;cursor:pointer;color:#adb5bd;font-size:1rem;padding:0;">
      <i class="fa-solid fa-xmark"></i>
    </button>
  `;

  container.appendChild(toast);

  // Add animation style once
  if (!document.getElementById('toastStyle')) {
    const style = document.createElement('style');
    style.id = 'toastStyle';
    style.textContent = `
      @keyframes slideIn {
        from { opacity: 0; transform: translateX(20px); }
        to   { opacity: 1; transform: translateX(0); }
      }
    `;
    document.head.appendChild(style);
  }

  setTimeout(() => toast.remove(), duration);
}

/* ── Date & Time Helpers ─────────────────────────────────────*/
function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function timeAgo(dateStr) {
  const now  = new Date();
  const past = new Date(dateStr);
  const diff = Math.floor((now - past) / 1000);

  if (diff < 60)     return 'Just now';
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return formatDate(dateStr);
}

/* ── String Helpers ──────────────────────────────────────────*/
function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function titleCase(str) {
  if (!str) return '';
  return str.replace(/_/g, ' ').replace(/\w\S*/g, w =>
    w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()
  );
}

/* ── Number Helpers ──────────────────────────────────────────*/
function formatNumber(num) {
  if (num === null || num === undefined) return '0';
  return Number(num).toLocaleString();
}

/* ── DOM Helper ──────────────────────────────────────────────*/
function setInnerHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}