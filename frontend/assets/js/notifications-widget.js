// assets/js/notifications-widget.js
//
// Self-contained notification bell: finds the bell button already present
// in the navbar (the .navbar-icon-btn containing a fa-bell icon), injects
// an unread badge and a dropdown panel, and wires them up against the
// confirmed /notifications API. Include this once per page, after api.js
// and utils.js:
//   <script src="../../assets/js/notifications-widget.js"></script>
//
// lab_result notifications now deep-link to laboratory.html?open_request=<id>
// using reference_type/reference_id returned by the API. Add more cases to
// getNotificationLink() below as other reference_type values come into use.

(function () {
  function findBellButton() {
    const buttons = document.querySelectorAll('.navbar-icon-btn');
    for (const btn of buttons) {
      if (btn.querySelector('.fa-bell')) return btn;
    }
    return null;
  }

  const bellBtn = findBellButton();
  if (!bellBtn) return; // page has no bell — nothing to attach to

  const typeMeta = {
    patient_flow: { icon: 'fa-layer-group', color: 'var(--primary)' },
    lab_result:   { icon: 'fa-flask',        color: '#e67e22' },
    low_stock:    { icon: 'fa-triangle-exclamation', color: 'var(--danger)' },
    system:       { icon: 'fa-gear',         color: 'var(--text-muted)' },
    general:      { icon: 'fa-bell',         color: 'var(--text-muted)' },
  };

  // Maps a notification's reference_type/reference_id to where clicking it
  // should go. Only lab_result is wired up for now.
  function getNotificationLink(n) {
    if (n.reference_type === 'lab_request' && n.reference_id) {
      return `laboratory.html?open_request=${n.reference_id}`;
    }
    return null;
  }

  /* ── Inject styles once ── */
  const style = document.createElement('style');
  style.textContent = `
    .notif-wrap { position: relative; display: inline-block; }
    .notif-badge {
      position: absolute; top: -2px; right: -2px;
      background: var(--danger); color: #fff; border-radius: 10px;
      font-size: 0.65rem; font-weight: 700; min-width: 16px; height: 16px;
      display: none; align-items: center; justify-content: center; padding: 0 4px;
    }
    .notif-dropdown {
      position: absolute; top: calc(100% + 10px); right: 0; width: 340px;
      max-height: 420px; background: var(--card-bg); border: 1px solid var(--border-light);
      border-radius: var(--border-radius); box-shadow: 0 10px 30px rgba(0,0,0,0.15);
      z-index: 1000; display: none; flex-direction: column; overflow: hidden;
    }
    .notif-dropdown.open { display: flex; }
    .notif-dropdown-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.85rem 1rem; border-bottom: 1px solid var(--border-light);
    }
    .notif-dropdown-header h4 { margin: 0; font-size: 0.92rem; color: var(--text-dark); }
    .notif-mark-all { background: none; border: none; color: var(--primary); font-size: 0.78rem; cursor: pointer; font-weight: 600; }
    .notif-list { overflow-y: auto; flex: 1; }
    .notif-item {
      display: flex; gap: 0.7rem; padding: 0.8rem 1rem; border-bottom: 1px solid var(--border-light);
      cursor: pointer; transition: background 0.12s;
    }
    .notif-item:hover { background: var(--page-bg); }
    .notif-item.unread { background: var(--primary-light); }
    .notif-item-icon {
      width: 32px; height: 32px; border-radius: 50%; background: var(--page-bg);
      display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 0.85rem;
    }
    .notif-item-title { font-size: 0.85rem; font-weight: 600; color: var(--text-dark); }
    .notif-item-msg { font-size: 0.8rem; color: var(--text-muted); margin-top: 2px; }
    .notif-item-time { font-size: 0.7rem; color: var(--text-light); margin-top: 4px; }
    .notif-empty { padding: 2rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.85rem; }
    .notif-dropdown-footer { padding: 0.65rem 1rem; text-align: center; border-top: 1px solid var(--border-light); }
    .notif-dropdown-footer a { font-size: 0.82rem; color: var(--primary); font-weight: 600; text-decoration: none; }
  `;
  document.head.appendChild(style);

  /* ── Inject badge + dropdown around the bell button ── */
  const wrap = document.createElement('div');
  wrap.className = 'notif-wrap';
  bellBtn.parentNode.insertBefore(wrap, bellBtn);
  wrap.appendChild(bellBtn);

  const badge = document.createElement('span');
  badge.className = 'notif-badge';
  wrap.appendChild(badge);

  const dropdown = document.createElement('div');
  dropdown.className = 'notif-dropdown';
  dropdown.innerHTML = `
    <div class="notif-dropdown-header">
      <h4>Notifications</h4>
      <button class="notif-mark-all" id="notifMarkAllBtn">Mark all as read</button>
    </div>
    <div class="notif-list" id="notifList">
      <div class="notif-empty">Loading...</div>
    </div>
    <div class="notif-dropdown-footer"><a href="notifications.html">View all</a></div>
  `;
  wrap.appendChild(dropdown);

  function timeAgoSafe(dateStr) {
    if (typeof timeAgo === 'function') return timeAgo(dateStr);
    return new Date(dateStr).toLocaleString();
  }

  async function refreshUnreadCount() {
    try {
      const res = await api.get('/notifications/unread-count');
      const count = res.data.unread_count || 0;
      if (count > 0) {
        badge.textContent = count > 9 ? '9+' : count;
        badge.style.display = 'flex';
      } else {
        badge.style.display = 'none';
      }
    } catch (e) { /* silent — badge just won't update this cycle */ }
  }

  async function loadDropdownList() {
    const list = document.getElementById('notifList');
    list.innerHTML = '<div class="notif-empty">Loading...</div>';
    try {
      const res = await api.get('/notifications?per_page=8');
      const notifs = res.data.notifications || [];
      if (!notifs.length) {
        list.innerHTML = '<div class="notif-empty">You\'re all caught up.</div>';
        return;
      }
      list.innerHTML = notifs.map(n => {
        const meta = typeMeta[n.notification_type] || typeMeta.general;
        return `
          <div class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}" data-link="${getNotificationLink(n) || ''}">
            <div class="notif-item-icon"><i class="fa-solid ${meta.icon}" style="color:${meta.color}"></i></div>
            <div style="flex:1;min-width:0">
              <div class="notif-item-title">${n.title}</div>
              <div class="notif-item-msg">${n.message}</div>
              <div class="notif-item-time">${timeAgoSafe(n.created_at)}</div>
            </div>
          </div>`;
      }).join('');
      list.querySelectorAll('.notif-item').forEach(el => {
        el.addEventListener('click', async () => {
          const id = parseInt(el.dataset.id, 10);
          const link = el.dataset.link;
          await markRead(id, el);
          if (link) window.location.href = link;
        });
      });
    } catch (e) {
      list.innerHTML = '<div class="notif-empty">Could not load notifications.</div>';
    }
  }

  async function markRead(id, el) {
    if (el && el.classList.contains('unread')) {
      el.classList.remove('unread');
      try { await api.patch(`/notifications/${id}/read`); refreshUnreadCount(); }
      catch (e) { /* non-critical */ }
    }
  }

  document.getElementById('notifMarkAllBtn')?.addEventListener('click', async (e) => {
    e.stopPropagation();
    try {
      await api.patch('/notifications/read-all');
      dropdown.querySelectorAll('.notif-item').forEach(el => el.classList.remove('unread'));
      refreshUnreadCount();
    } catch (err) { /* non-critical */ }
  });

  bellBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('open');
    if (dropdown.classList.contains('open')) loadDropdownList();
  });
  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) dropdown.classList.remove('open');
  });

  refreshUnreadCount();
  setInterval(refreshUnreadCount, 30000);
})();