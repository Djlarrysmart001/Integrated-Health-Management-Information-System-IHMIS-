/* ============================================================
   IHMIS — api.js
   ============================================================ */

const API_BASE = 'http://127.0.0.1:5000/api/v1';

async function apiRequest(endpoint, method = 'GET', body = null) {
  const token = localStorage.getItem('ihmis_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const config = { method, headers };
  if (body) config.body = JSON.stringify(body);

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, config);
    const data = await response.json();

    if (!response.ok) {
      if (response.status === 401) {
        clearSession();
        window.location.href = '/index.html';
        return;
      }
      throw new Error(data.message || data.msg || 'Request failed');
    }

    return data;
  } catch (error) {
    if (error.message === 'Failed to fetch') {
      throw new Error('Cannot connect to server. Make sure Flask is running on port 5000.');
    }
    throw error;
  }
}

const api = {
  get:    (endpoint)       => apiRequest(endpoint, 'GET'),
  post:   (endpoint, body) => apiRequest(endpoint, 'POST', body),
  put:    (endpoint, body) => apiRequest(endpoint, 'PUT', body),
  patch:  (endpoint, body) => apiRequest(endpoint, 'PATCH', body),
  delete: (endpoint)       => apiRequest(endpoint, 'DELETE'),
};

function saveSession(token, user) {
  localStorage.setItem('ihmis_token', token);
  localStorage.setItem('ihmis_user', JSON.stringify(user));
}

function getUser() {
  const u = localStorage.getItem('ihmis_user');
  return u ? JSON.parse(u) : null;
}

function clearSession() {
  localStorage.removeItem('ihmis_token');
  localStorage.removeItem('ihmis_user');
}

function isLoggedIn() {
  return !!localStorage.getItem('ihmis_token');
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