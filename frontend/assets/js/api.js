/* ============================================================
   IHMIS — api.js
   ============================================================ */

// Local dev via VS Code Live Server serves the frontend on its own port
// (5500) while Flask runs separately on 5000 -- two different origins,
// so API calls must point at the backend explicitly in that one case.
// Everywhere else (Render, or any setup where Flask itself serves the
// frontend), frontend and backend share the same origin, so a relative
// path always resolves correctly regardless of the actual domain --
// this is what makes the deployed app portable across environments
// without a code change.
const API_BASE = (
  (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost')
  && window.location.port === '5500'
) ? 'http://127.0.0.1:5000/api/v1' : '/api/v1';

// ── UTC timestamp fix ─────────────────────────────────────────
// The backend stores datetimes correctly as UTC (datetime.now(timezone.utc)),
// but MySQL's DATETIME column type has no concept of timezone -- it silently
// strips the tzinfo on write. When SQLAlchemy reads the value back and the
// model calls .isoformat(), the result is a naive string with no "Z" or
// "+00:00" suffix, e.g. "2026-09-08T11:41:00" instead of
// "2026-09-08T11:41:00Z". new Date() on a string with no timezone marker is
// interpreted as LOCAL time, not UTC -- so every "time ago" / wait-time
// calculation across the app comes out shifted by the browser's UTC offset
// (exactly +1h in Lagos/WAT, which is why it always showed ~1h too much).
//
// Rather than patch this at 30+ call sites across 18 files, every API
// response is walked once here and any bare ISO datetime string (one that
// has a "T" time component but no trailing Z/+hh:mm/-hh:mm) gets a "Z"
// appended, so it is always parsed as UTC everywhere in the app.
const BARE_ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/;

function fixServerDates(value) {
  if (Array.isArray(value)) {
    return value.map(fixServerDates);
  }
  if (value && typeof value === 'object') {
    for (const key in value) {
      if (Object.prototype.hasOwnProperty.call(value, key)) {
        value[key] = fixServerDates(value[key]);
      }
    }
    return value;
  }
  if (typeof value === 'string' && BARE_ISO_DATETIME.test(value)) {
    return value + 'Z';
  }
  return value;
}

async function apiRequest(endpoint, method = 'GET', body = null, isRetry = false) {
  const token = sessionStorage.getItem('ihmis_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const config = { method, headers };
  if (body) config.body = JSON.stringify(body);

  // fetch() has no built-in timeout -- on a network that silently drops
  // packets (common on restrictive/filtered WiFi) instead of actively
  // refusing the connection, a request can hang forever with no error
  // ever firing. This AbortController forces it to fail after 15s so the
  // UI can show a real error instead of spinning/"Loading..." indefinitely.
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  config.signal = controller.signal;

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    clearTimeout(timeoutId);
    let data = await response.json();
    data = fixServerDates(data);

    if (!response.ok) {
      // The access token is deliberately short-lived (15 min by default).
      // Before this fix, a 401 here went straight to a forced logout, so
      // anyone mid-consultation got kicked back to the login screen the
      // moment the token expired, even though the backend has always had
      // a working /auth/refresh endpoint -- the frontend just never called
      // it. Now: on a 401 (and only once, and never for the login/refresh
      // calls themselves), try a silent refresh and retry the original
      // request before giving up.
      if (response.status === 401 && !isRetry && endpoint !== '/auth/refresh' && endpoint !== '/auth/login') {
        const refreshed = await tryRefreshToken();
        if (refreshed) {
          return apiRequest(endpoint, method, body, true);
        }
      }
      if (response.status === 401) {
        clearSession();
        window.location.href = '/index.html';
        return;
      }
      throw new Error(data.message || data.msg || 'Request failed');
    }

    return data;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out — check your network connection.');
    }
    if (error.message === 'Failed to fetch') {
      throw new Error('Cannot connect to server. Check your internet connection.');
    }
    throw error;
  }
}

// Uses the long-lived refresh token (7 days) to silently obtain a new
// access token. Returns true/false rather than throwing, since a failed
// refresh should just fall through to the normal forced-logout path in
// apiRequest above, not surface its own error.
async function tryRefreshToken() {
  const refreshToken = sessionStorage.getItem('ihmis_refresh_token');
  if (!refreshToken) return false;
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${refreshToken}` },
    });
    if (!response.ok) return false;
    const data = await response.json();
    const newAccessToken = data?.data?.access_token;
    if (!newAccessToken) return false;
    sessionStorage.setItem('ihmis_token', newAccessToken);
    return true;
  } catch (err) {
    return false;
  }
}

const api = {
  get:    (endpoint)       => apiRequest(endpoint, 'GET'),
  post:   (endpoint, body) => apiRequest(endpoint, 'POST', body),
  put:    (endpoint, body) => apiRequest(endpoint, 'PUT', body),
  patch:  (endpoint, body) => apiRequest(endpoint, 'PATCH', body),
  delete: (endpoint)       => apiRequest(endpoint, 'DELETE'),
};

// ── Authenticated image loading ─────────────────────────────────
// A plain <img src="..."> request never carries the Authorization
// header, so pointing one directly at a JWT-protected endpoint (e.g.
// the patient photo route) 401s on every real page load/refresh --
// it only ever looked fine right after an upload because that preview
// came from a local FileReader data URI, not this endpoint. This
// fetches the bytes with the token attached and hands back a local
// blob URL that an <img> can use safely.
async function loadAuthImage(url) {
  const token = sessionStorage.getItem('ihmis_token');
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error('Could not load image');
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

// NOTE: sessionStorage (not localStorage) is deliberate here. localStorage
// is shared across every tab of the same origin, so with multiple role
// portals open in different tabs, logging into one would silently
// overwrite the session every other tab was reading -- causing random
// "jumps" to whichever role most recently logged in anywhere in the
// browser. sessionStorage is isolated per tab, so each open portal keeps
// its own independent session.
function saveSession(token, user, refreshToken) {
  sessionStorage.setItem('ihmis_token', token);
  sessionStorage.setItem('ihmis_user', JSON.stringify(user));
  if (refreshToken) sessionStorage.setItem('ihmis_refresh_token', refreshToken);
}

function getUser() {
  const u = sessionStorage.getItem('ihmis_user');
  return u ? JSON.parse(u) : null;
}

function clearSession() {
  sessionStorage.removeItem('ihmis_token');
  sessionStorage.removeItem('ihmis_user');
  sessionStorage.removeItem('ihmis_refresh_token');
}

function isLoggedIn() {
  return !!sessionStorage.getItem('ihmis_token');
}

function redirectByRole(role) {
  const routes = {
    admin:      '/pages/admin/dashboard.html',
    doctor:     '/pages/doctor/dashboard.html',
    pharmacist: '/pages/pharmacist/dashboard.html',
    lab_tech:   '/pages/lab/dashboard.html',
    nurse:      '/pages/nurse/dashboard.html',
    mho:        '/pages/mho/dashboard.html',
  };
  const path = routes[role];
  if (path) {
    window.location.href = path;
  } else {
    console.error('Unknown role:', role);
  }
}

function requireAuth(requiredRole = null) {
  /*
   * IMPORTANT: Only call this from DASHBOARD pages, never from index.html.
   * Dashboard pages are 2 levels deep: pages/admin/dashboard.html
   * So redirect back uses ../../index.html
   */
  if (!isLoggedIn()) {
    window.location.href = '/index.html';
    return null;
  }
  const user = getUser();
  if (requiredRole && user.role !== requiredRole) {
    redirectByRole(user.role);
    return null;
  }
  return user;
}