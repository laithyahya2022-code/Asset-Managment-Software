/* ITAM Platform — web client (no build step, talks to the REST API) */
'use strict';

const API = '/api/v1';
const S = {
  token: localStorage.getItem('itam.token') || null,
  user: JSON.parse(localStorage.getItem('itam.user') || 'null'),
  lists: {}, // cached reference lists (categories, branches, …)
};

/* ── tiny DOM + net helpers ─────────────────────────────────────── */
const $ = (sel, root = document) => root.querySelector(sel);
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) node.setAttribute(k, v);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child.nodeType ? child : document.createTextNode(child));
  }
  return node;
}
function toast(message, isError = false) {
  const t = el('div', { class: 'toast' + (isError ? ' err' : '') }, message);
  $('#toasts').append(t);
  setTimeout(() => t.remove(), isError ? 6000 : 3200);
}
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  if (S.token) headers.Authorization = 'Bearer ' + S.token;
  const res = await fetch(API + path, { ...options, headers });
  if (res.status === 401 && S.token) { logout(); throw new Error('Session expired — please sign in again'); }
  if (res.status === 204) return null;
  const isJson = (res.headers.get('content-type') || '').includes('json');
  const body = isJson ? await res.json() : await res.blob();
  if (!res.ok) {
    const msg = Array.isArray(body?.message) ? body.message.join('; ') : body?.message || 'Request failed';
    throw new Error(msg);
  }
  return body;
}
async function authedImageURL(path) {
  const blob = await api(path);
  return URL.createObjectURL(blob);
}
const fmtDate = (value) => (value ? new Date(value).toLocaleDateString() : '—');
const fmtDateTime = (value) => (value ? new Date(value).toLocaleString() : '—');
const fmtMoney = (value) => (value === null || value === undefined ? '—' : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 }));
const titleCase = (s) => (s || '').toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const pill = (status) => el('span', { class: `pill s-${status}` }, el('span', { class: 'dot' }), titleCase(status));

function modal(title, body, { wide = false } = {}) {
  const overlay = el('div', { class: 'overlay', onclick: (e) => { if (e.target === overlay) overlay.remove(); } },
    el('div', { class: 'modal' + (wide ? ' wide' : '') }, el('h3', {}, title), body),
  );
  document.body.append(overlay);
  return overlay;
}
function field(label, input) { return el('div', { class: 'field' }, el('label', {}, label), input); }
function input(name, attrs = {}) { return el('input', { name, ...attrs }); }
function select(name, options, attrs = {}) {
  return el('select', { name, ...attrs }, options.map((o) => el('option', { value: o.value }, o.label)));
}
function formData(form) {
  const out = {};
  for (const [k, v] of new FormData(form).entries()) if (v !== '') out[k] = v;
  return out;
}

/* reference lists for dropdowns (cached) */
async function refList(kind) {
  if (!S.lists[kind]) {
    const page = await api(`/${kind}?pageSize=200`);
    S.lists[kind] = page.items;
  }
  return S.lists[kind];
}
const refOptions = (items, labelFn, blank = '— none —') => [
  { value: '', label: blank },
  ...items.map((i) => ({ value: i.id, label: labelFn(i) })),
];
const nameOf = (kind, id) => {
  const hit = (S.lists[kind] || []).find((i) => i.id === id);
  return hit ? hit.name || hit.fullName : id ? '…' : '—';
};

/* ── auth ───────────────────────────────────────────────────────── */
function saveSession(session) {
  S.token = session.accessToken;
  S.user = session.user;
  localStorage.setItem('itam.token', session.accessToken);
  localStorage.setItem('itam.user', JSON.stringify(session.user));
}
function logout() {
  S.token = null; S.user = null; S.lists = {};
  localStorage.removeItem('itam.token');
  localStorage.removeItem('itam.user');
  location.hash = '';
  render();
}

function renderAuth() {
  const root = $('#root');
  root.innerHTML = '';
  let mode = 'login';

  const body = el('div');
  const tabs = el('div', { class: 'tabs' },
    el('button', { class: 'active', onclick: (e) => switchMode('login', e.target) }, 'Sign in'),
    el('button', { onclick: (e) => switchMode('register', e.target) }, 'Create organization'),
  );
  function switchMode(m, btn) {
    mode = m;
    tabs.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    drawForm();
  }
  function drawForm() {
    body.innerHTML = '';
    const form = el('form', {
      onsubmit: async (e) => {
        e.preventDefault();
        const btn = form.querySelector('button[type=submit]');
        btn.disabled = true;
        try {
          const data = formData(form);
          const session = mode === 'login'
            ? await api('/auth/login', { method: 'POST', body: data })
            : await api('/auth/register-organization', { method: 'POST', body: data });
          saveSession(session);
          toast(mode === 'login' ? `Welcome back, ${session.user.fullName}` : 'Organization created — welcome!');
          location.hash = '#/dashboard';
          render();
        } catch (err) { toast(err.message, true); btn.disabled = false; }
      },
    });
    if (mode === 'login') {
      form.append(
        field('Email', input('email', { type: 'email', required: true, placeholder: 'you@company.com' })),
        field('Password', input('password', { type: 'password', required: true })),
        el('button', { class: 'btn primary block', type: 'submit' }, 'Sign in'),
      );
    } else {
      form.append(
        field('Organization name', input('organizationName', { required: true, placeholder: 'Acme Corporation' })),
        field('Organization ID (letters/numbers, no spaces)', input('organizationSlug', { required: true, placeholder: 'acme', pattern: '[a-z0-9][a-z0-9\\-]{1,98}[a-z0-9]' })),
        field('Your full name', input('adminFullName', { required: true })),
        field('Your email', input('adminEmail', { type: 'email', required: true })),
        field('Password (min 10 characters)', input('adminPassword', { type: 'password', required: true, minlength: 10 })),
        el('button', { class: 'btn primary block', type: 'submit' }, 'Create organization'),
      );
    }
    body.append(form);
  }
  drawForm();

  root.append(el('div', { class: 'auth-wrap' },
    el('div', { class: 'auth-card' },
      el('div', { class: 'brand' }, el('div', { class: 'brand-mark' }, 'IT'), el('h1', {}, 'ITAM Platform')),
      el('p', { class: 'auth-sub' }, 'Enterprise IT asset management'),
      tabs, body,
    ),
  ));
}

/* ── layout ─────────────────────────────────────────────────────── */
const NAV = [
  { hash: '#/dashboard', icon: '📊', label: 'Dashboard' },
  { hash: '#/assets', icon: '💻', label: 'Assets' },
  { hash: '#/employees', icon: '👥', label: 'Employees' },
  { hash: '#/licenses', icon: '🔑', label: 'Licenses' },
  { hash: '#/maintenance', icon: '🛠️', label: 'Maintenance' },
  { hash: '#/reports', icon: '📄', label: 'Reports' },
  { sect: 'Administration' },
  { hash: '#/structure', icon: '🏢', label: 'Organization' },
  { hash: '#/audit', icon: '🛡️', label: 'Audit Trail' },
];

function renderApp() {
  const root = $('#root');
  root.innerHTML = '';
  const view = el('div', { id: 'view' });
  const title = el('h2', { id: 'page-title' }, '');

  const bellBadge = el('span', { class: 'badge', style: 'display:none' });
  const bellWrap = el('div', { class: 'bell', style: 'position:relative' },
    el('button', { class: 'btn', onclick: toggleNotifications, title: 'Notifications' }, '🔔', bellBadge),
  );
  async function refreshUnread() {
    try {
      const { unread } = await api('/notifications/unread-count');
      bellBadge.style.display = unread ? 'grid' : 'none';
      bellBadge.textContent = unread > 99 ? '99+' : unread;
    } catch { /* ignore */ }
  }
  async function toggleNotifications() {
    const existing = bellWrap.querySelector('.dropdown');
    if (existing) { existing.remove(); return; }
    const page = await api('/notifications?pageSize=15');
    const dropdown = el('div', { class: 'dropdown' },
      el('div', { class: 'flex', style: 'justify-content:space-between;padding:4px 8px' },
        el('b', {}, 'Notifications'),
        el('button', { class: 'btn sm', onclick: async () => { await api('/notifications/read-all', { method: 'POST' }); dropdown.remove(); refreshUnread(); } }, 'Mark all read'),
      ),
      page.items.length === 0 ? el('div', { class: 'empty' }, 'Nothing yet') :
        page.items.map((n) => el('div', { class: 'note' + (n.isRead ? '' : ' unread') },
          el('b', {}, n.title), el('span', {}, n.message),
          el('div', { class: 'muted', style: 'font-size:11px' }, fmtDateTime(n.createdAt)),
        )),
    );
    bellWrap.append(dropdown);
  }

  root.append(el('div', { class: 'app' },
    el('aside', { class: 'sidebar' },
      el('div', { class: 'brand' }, el('div', { class: 'brand-mark' }, 'IT'), el('h1', {}, 'ITAM')),
      el('nav', { class: 'nav' }, NAV.map((item) =>
        item.sect
          ? el('div', { class: 'sect' }, item.sect)
          : el('a', { href: item.hash, 'data-nav': item.hash },
              el('span', { class: 'ico' }, item.icon), el('span', { class: 'txt' }, item.label)),
      )),
    ),
    el('div', { class: 'main' },
      el('div', { class: 'topbar' },
        title,
        el('div', { class: 'spacer' }),
        bellWrap,
        el('div', { class: 'userchip' },
          el('div', { class: 'avatar' }, (S.user.fullName || '?').split(' ').map((w) => w[0]).slice(0, 2).join('')),
          el('div', { class: 'who' }, el('b', {}, S.user.fullName), el('span', {}, S.user.role)),
        ),
        el('button', { class: 'btn sm', onclick: () => { api('/auth/logout', { method: 'POST' }).catch(() => {}); logout(); } }, 'Sign out'),
      ),
      view,
    ),
  ));
  refreshUnread();
  return { view, title };
}

/* ── charts: single-series horizontal bar list ──────────────────── */
function barList(rows, labelFn) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return el('div', { class: 'barlist' }, rows.map((r) =>
    el('div', { class: 'row', title: `${labelFn(r.key)}: ${r.count}` },
      el('div', { class: 'lbl' }, labelFn(r.key)),
      el('div', { class: 'track' }, el('div', { class: 'bar', style: `width:${(r.count / max) * 100}%` })),
      el('div', { class: 'num' }, r.count),
    ),
  ));
}

/* ── views ──────────────────────────────────────────────────────── */
async function viewDashboard(view) {
  const [summary] = await Promise.all([api('/dashboard'), refList('categories'), refList('branches')]);
  const t = summary.totals;
  const tiles = [
    ['Total assets', t.totalAssets],
    ['Assigned', t.assignedAssets],
    ['Available', t.availableAssets],
    ['In maintenance', t.maintenanceAssets],
    ['Retired', t.retiredAssets],
    ['Warranty expiring (90d)', t.warrantyExpiring90d, t.warrantyExpiring90d > 0],
    ['Licenses expiring (90d)', t.licenseExpiring90d, t.licenseExpiring90d > 0],
    ['Overdue returns', t.overdueReturns, t.overdueReturns > 0],
  ];
  const f = summary.financials;
  view.append(
    el('div', { class: 'cards' },
      tiles.map(([k, v, alert]) => el('div', { class: 'tile' },
        el('div', { class: 'k' }, k), el('div', { class: 'v' + (alert ? ' alert' : '') }, v),
      )),
    ),
    el('div', { class: 'cards' },
      el('div', { class: 'tile' }, el('div', { class: 'k' }, 'Total purchase cost'), el('div', { class: 'v' }, fmtMoney(f.totalPurchaseCost)), el('div', { class: 'sub' }, 'all assets')),
      el('div', { class: 'tile' }, el('div', { class: 'k' }, 'Current book value'), el('div', { class: 'v' }, fmtMoney(f.currentBookValue)), el('div', { class: 'sub' }, 'straight-line depreciation')),
      el('div', { class: 'tile' }, el('div', { class: 'k' }, 'Accumulated depreciation'), el('div', { class: 'v' }, fmtMoney(f.accumulatedDepreciation))),
      el('div', { class: 'tile' }, el('div', { class: 'k' }, 'Maintenance spend'), el('div', { class: 'v' }, fmtMoney(f.maintenanceSpend)), el('div', { class: 'sub' }, 'completed work orders')),
    ),
    el('div', { class: 'grid-2' },
      el('div', { class: 'panel' }, el('h3', {}, 'Assets by status'),
        summary.breakdowns.byStatus.length ? barList(summary.breakdowns.byStatus.sort((a, b) => b.count - a.count), titleCase) : el('div', { class: 'empty' }, 'No assets yet')),
      el('div', { class: 'panel' }, el('h3', {}, 'Assets by category'),
        summary.breakdowns.byCategory.length ? barList(summary.breakdowns.byCategory.sort((a, b) => b.count - a.count), (id) => nameOf('categories', id)) : el('div', { class: 'empty' }, 'No assets yet')),
    ),
    el('div', { class: 'panel' }, el('h3', {}, 'Recent activity'),
      summary.recentActivity.length === 0 ? el('div', { class: 'empty' }, 'Activity will appear here') :
        el('ul', { class: 'feed' }, summary.recentActivity.map((e) =>
          el('li', {}, el('span', { class: 't' }, fmtDateTime(e.createdAt)), el('span', {}, e.description)),
        )),
    ),
  );
}

/* ---- assets ---- */
const ASSET_STATUSES = ['PLANNED','PURCHASE_REQUESTED','APPROVED','ORDERED','RECEIVED','IN_STOCK','DEPLOYED','ASSIGNED','IN_MAINTENANCE','IN_REPAIR','IN_TRANSFER','RETIRED','DISPOSED','LOST'];
const CONDITIONS = ['NEW','EXCELLENT','GOOD','FAIR','POOR','DAMAGED','FOR_PARTS'];

async function viewAssets(view) {
  await Promise.all([refList('categories'), refList('branches'), refList('departments'), refList('employees'), refList('suppliers')]);
  let page = 1, search = '', status = '';
  const tableWrap = el('div');

  async function load() {
    tableWrap.innerHTML = '';
    const params = new URLSearchParams({ page, pageSize: 15 });
    if (search) params.set('search', search);
    if (status) params.set('status', status);
    const data = await api('/assets?' + params);
    if (data.items.length === 0) { tableWrap.append(el('div', { class: 'empty' }, 'No assets found. Click "New asset" to add your first one.')); return; }
    tableWrap.append(
      el('table', { class: 'data' },
        el('thead', {}, el('tr', {}, ['Tag', 'Name', 'Category', 'Status', 'Assigned to', 'Branch', 'Cost', 'Warranty end'].map((h) => el('th', {}, h)))),
        el('tbody', {}, data.items.map((a) => el('tr', { class: 'click', onclick: () => assetDetail(a.id, load) },
          el('td', {}, el('b', {}, a.assetTag)),
          el('td', {}, a.name),
          el('td', {}, nameOf('categories', a.categoryId)),
          el('td', {}, pill(a.status)),
          el('td', {}, nameOf('employees', a.assignedEmployeeId)),
          el('td', {}, nameOf('branches', a.branchId)),
          el('td', { class: 'num' }, fmtMoney(a.purchaseCost)),
          el('td', {}, fmtDate(a.warrantyEndDate)),
        ))),
      ),
      el('div', { class: 'pager' },
        el('button', { class: 'btn sm', disabled: page <= 1 || null, onclick: () => { page--; load(); } }, '← Prev'),
        el('span', {}, `Page ${data.page} of ${data.totalPages} — ${data.total} assets`),
        el('button', { class: 'btn sm', disabled: page >= data.totalPages || null, onclick: () => { page++; load(); } }, 'Next →'),
      ),
    );
  }

  let debounce;
  view.append(
    el('div', { class: 'toolbar' },
      el('input', { type: 'search', placeholder: 'Search tag, serial, name, model…', oninput: (e) => { clearTimeout(debounce); debounce = setTimeout(() => { search = e.target.value; page = 1; load(); }, 350); } }),
      select('status', [{ value: '', label: 'All statuses' }, ...ASSET_STATUSES.map((s) => ({ value: s, label: titleCase(s) }))], { onchange: (e) => { status = e.target.value; page = 1; load(); } }),
      el('div', { class: 'spacer', style: 'flex:1' }),
      el('button', { class: 'btn primary', onclick: () => assetForm(load) }, '＋ New asset'),
    ),
    el('div', { class: 'panel' }, tableWrap),
  );
  await load();
}

function assetForm(onDone) {
  const cats = S.lists.categories || [];
  const form = el('form', { class: 'form-grid' },
    field('Name *', input('name', { required: true, class: 'span-2', placeholder: 'e.g. MacBook Pro 14 — Design team' })).classList.add('span-2') ||
    null,
  );
  form.innerHTML = '';
  const f = (lbl, node, span2 = false) => { const w = field(lbl, node); if (span2) w.classList.add('span-2'); return w; };
  form.append(
    f('Name *', input('name', { required: true, placeholder: 'e.g. MacBook Pro 14" — Design team' }), true),
    f('Category *', select('categoryId', cats.map((c) => ({ value: c.id, label: c.name })), { required: true })),
    f('Serial number', input('serialNumber')),
    f('Manufacturer', input('manufacturer')),
    f('Model', input('model')),
    f('Purchase date', input('purchaseDate', { type: 'date' })),
    f('Purchase cost', input('purchaseCost', { type: 'number', step: '0.01', min: 0 })),
    f('Warranty start', input('warrantyStartDate', { type: 'date' })),
    f('Warranty end', input('warrantyEndDate', { type: 'date' })),
    f('Branch', select('branchId', refOptions(S.lists.branches || [], (b) => b.name))),
    f('Department', select('departmentId', refOptions(S.lists.departments || [], (d) => d.name))),
    f('Supplier', select('supplierId', refOptions(S.lists.suppliers || [], (s) => s.name))),
    f('Condition', select('condition', CONDITIONS.map((c) => ({ value: c, label: titleCase(c) })))),
    f('Location / room', input('room')),
    f('Notes', el('textarea', { name: 'notes', rows: 2 }), true),
  );
  const overlay = modal('New asset', el('div', {},
    cats.length === 0 ? el('p', { class: 'muted' }, 'Tip: create a category first (Organization → Categories) — added a default for you if none exists.') : null,
    form,
    el('div', { class: 'actions' },
      el('button', { class: 'btn', onclick: () => overlay.remove() }, 'Cancel'),
      el('button', { class: 'btn primary', onclick: async (e) => {
        e.target.disabled = true;
        try {
          let body = formData(form);
          if (body.purchaseCost) body.purchaseCost = Number(body.purchaseCost);
          if (!body.categoryId) {
            const cat = await api('/categories', { method: 'POST', body: { name: 'General', code: 'GEN' } });
            S.lists.categories = null; body.categoryId = cat.id;
          }
          const asset = await api('/assets', { method: 'POST', body });
          toast(`Asset ${asset.assetTag} created`);
          overlay.remove(); onDone();
        } catch (err) { toast(err.message, true); e.target.disabled = false; }
      } }, 'Create asset'),
    ),
  ), { wide: true });
}

async function assetDetail(id, onChange) {
  const asset = await api('/assets/' + id);
  const dep = asset.depreciation;
  const body = el('div');
  const overlay = modal(`${asset.assetTag} — ${asset.name}`, body, { wide: true });

  async function reload() { overlay.remove(); assetDetail(id, onChange); onChange(); }

  const actions = el('div', { class: 'chips' });
  // lifecycle transition
  actions.append(el('button', { class: 'btn sm', onclick: () => {
    const sel = select('status', ASSET_STATUSES.filter((s) => s !== 'ASSIGNED' && s !== asset.status).map((s) => ({ value: s, label: titleCase(s) })));
    const reason = input('reason', { placeholder: 'Reason (optional)' });
    const m = modal('Change lifecycle status', el('div', {},
      field('New status', sel), field('Reason', reason),
      el('div', { class: 'actions' },
        el('button', { class: 'btn', onclick: () => m.remove() }, 'Cancel'),
        el('button', { class: 'btn primary', onclick: async (e) => {
          e.target.disabled = true;
          try { await api(`/assets/${id}/transition`, { method: 'POST', body: { status: sel.value, reason: reason.value || undefined } }); toast('Status updated'); m.remove(); reload(); }
          catch (err) { toast(err.message, true); e.target.disabled = false; }
        } }, 'Apply'),
      ),
    ));
  } }, 'Change status'));

  if (['IN_STOCK', 'DEPLOYED'].includes(asset.status)) {
    actions.append(el('button', { class: 'btn sm primary', onclick: () => checkOutModal(asset, reload) }, 'Check out →'));
  }
  if (asset.status === 'ASSIGNED') {
    actions.append(el('button', { class: 'btn sm primary', onclick: async () => {
      const active = await api(`/assignments?assetId=${id}&status=ACTIVE&pageSize=1`);
      if (!active.items.length) return toast('No active assignment found', true);
      checkInModal(active.items[0], reload);
    } }, '← Check in'));
  }

  const history = await api(`/assets/${id}/history?pageSize=30`);
  body.append(
    el('div', { class: 'detail-grid' },
      el('div', {},
        el('div', { class: 'flex', style: 'margin-bottom:12px' }, pill(asset.status), el('span', { class: 'pill' }, el('span', { class: 'dot' }), titleCase(asset.condition))),
        el('dl', { class: 'kv' },
          ...[
            ['Serial number', asset.serialNumber || '—'],
            ['Manufacturer', asset.manufacturer || '—'],
            ['Model', asset.model || '—'],
            ['Category', nameOf('categories', asset.categoryId)],
            ['Assigned to', nameOf('employees', asset.assignedEmployeeId)],
            ['Branch', nameOf('branches', asset.branchId)],
            ['Department', nameOf('departments', asset.departmentId)],
            ['Location', [asset.building, asset.floor, asset.room].filter(Boolean).join(' / ') || '—'],
            ['Purchase date', fmtDate(asset.purchaseDate)],
            ['Purchase cost', fmtMoney(asset.purchaseCost)],
            ['Warranty', asset.warrantyEndDate ? `${fmtDate(asset.warrantyStartDate)} → ${fmtDate(asset.warrantyEndDate)}` : '—'],
            ['Book value', dep ? `${fmtMoney(dep.currentBookValue)} (of ${fmtMoney(dep.purchaseCost)})` : '—'],
            ['Notes', asset.notes || '—'],
          ].flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, String(v))]),
        ),
        el('h3', { style: 'margin-top:18px' }, 'Actions'), actions,
        el('h3', { style: 'margin-top:18px' }, 'History'),
        el('ul', { class: 'timeline' }, history.items.map((h) =>
          el('li', {}, el('div', {}, h.description), el('div', { class: 't' }, fmtDateTime(h.createdAt))),
        )),
      ),
      el('div', { class: 'label-imgs' },
        el('h3', { class: 'mb0' }, 'Labels'),
        el('p', { class: 'muted', style: 'margin:4px 0 10px' }, 'Print these on the device. Scanning resolves the asset instantly.'),
        el('div', { id: 'qr-slot' }, el('div', { class: 'empty' }, 'Loading…')),
      ),
    ),
  );
  // load QR + barcode with auth
  try {
    const [qr, bc] = await Promise.all([
      authedImageURL(`/assets/${id}/qrcode`),
      authedImageURL(`/assets/${id}/barcode`),
    ]);
    const slot = body.querySelector('#qr-slot');
    slot.innerHTML = '';
    slot.append(el('img', { src: qr, alt: 'QR code' }), el('img', { src: bc, alt: 'Barcode' }));
  } catch { /* label render best-effort */ }
}

function signaturePad() {
  const canvas = el('canvas', { width: 560, height: 130, style: 'width:100%;border:1px dashed var(--baseline);border-radius:8px;background:#fff;touch-action:none' });
  const ctx = canvas.getContext('2d');
  ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.strokeStyle = '#0b0b0b';
  let drawing = false; let dirty = false;
  const pos = (e) => {
    const r = canvas.getBoundingClientRect();
    return [((e.clientX - r.left) * canvas.width) / r.width, ((e.clientY - r.top) * canvas.height) / r.height];
  };
  canvas.addEventListener('pointerdown', (e) => { drawing = true; ctx.beginPath(); ctx.moveTo(...pos(e)); });
  canvas.addEventListener('pointermove', (e) => { if (drawing) { ctx.lineTo(...pos(e)); ctx.stroke(); dirty = true; } });
  window.addEventListener('pointerup', () => { drawing = false; });
  return { canvas, value: () => (dirty ? canvas.toDataURL('image/png') : undefined), clear: () => { ctx.clearRect(0, 0, canvas.width, canvas.height); dirty = false; } };
}

function checkOutModal(asset, onDone) {
  const employees = (S.lists.employees || []).filter((e) => e.isActive);
  const empSel = select('employeeId', employees.map((e) => ({ value: e.id, label: `${e.fullName} (${e.employeeNumber})` })));
  const due = input('expectedReturnAt', { type: 'date' });
  const notes = input('notes', { placeholder: 'e.g. new starter kit' });
  const sig = signaturePad();
  const m = modal(`Check out ${asset.assetTag}`, el('div', {},
    employees.length === 0 ? el('p', { class: 'muted' }, 'No employees yet — add one under Employees first.') : null,
    field('Assign to employee', empSel),
    field('Expected return (optional)', due),
    field('Notes', notes),
    field('Employee signature (draw with mouse or finger)', sig.canvas),
    el('button', { class: 'btn sm', onclick: sig.clear }, 'Clear signature'),
    el('div', { class: 'actions' },
      el('button', { class: 'btn', onclick: () => m.remove() }, 'Cancel'),
      el('button', { class: 'btn primary', disabled: employees.length === 0 || null, onclick: async (e) => {
        e.target.disabled = true;
        try {
          await api('/assignments/check-out', { method: 'POST', body: {
            assetId: asset.id, employeeId: empSel.value,
            expectedReturnAt: due.value ? new Date(due.value).toISOString() : undefined,
            notes: notes.value || undefined, signature: sig.value(),
          } });
          toast('Asset checked out'); m.remove(); onDone();
        } catch (err) { toast(err.message, true); e.target.disabled = false; }
      } }, 'Check out'),
    ),
  ), { wide: true });
}

function checkInModal(assignment, onDone) {
  const cond = select('condition', CONDITIONS.map((c) => ({ value: c, label: titleCase(c) })));
  cond.value = 'GOOD';
  const damage = input('damageNotes', { placeholder: 'Damage notes (optional)' });
  const sig = signaturePad();
  const m = modal('Check in asset', el('div', {},
    field('Condition on return', cond),
    field('Damage notes', damage),
    field('Signature', sig.canvas),
    el('div', { class: 'actions' },
      el('button', { class: 'btn', onclick: () => m.remove() }, 'Cancel'),
      el('button', { class: 'btn primary', onclick: async (e) => {
        e.target.disabled = true;
        try {
          await api(`/assignments/${assignment.id}/check-in`, { method: 'POST', body: {
            condition: cond.value, damageNotes: damage.value || undefined, signature: sig.value(),
          } });
          toast('Asset returned to stock'); m.remove(); onDone();
        } catch (err) { toast(err.message, true); e.target.disabled = false; }
      } }, 'Check in'),
    ),
  ));
}

/* ---- employees ---- */
async function viewEmployees(view) {
  await Promise.all([refList('departments'), refList('branches')]);
  const wrap = el('div');
  async function load() {
    S.lists.employees = null;
    const data = await api('/employees?pageSize=100');
    S.lists.employees = data.items;
    wrap.innerHTML = '';
    if (!data.items.length) { wrap.append(el('div', { class: 'empty' }, 'No employees yet.')); return; }
    wrap.append(el('table', { class: 'data' },
      el('thead', {}, el('tr', {}, ['Number', 'Name', 'Email', 'Job title', 'Department', 'Branch', 'Assets held'].map((h) => el('th', {}, h)))),
      el('tbody', {}, data.items.map((emp) => {
        const holdCell = el('td', {}, el('button', { class: 'btn sm', onclick: async () => {
          const assets = await api(`/assignments/employee/${emp.id}/assets`);
          modal(`Assets held by ${emp.fullName}`, el('div', {},
            assets.length === 0 ? el('div', { class: 'empty' }, 'None currently') :
              el('table', { class: 'data' }, el('tbody', {}, assets.map((a) => el('tr', {}, el('td', {}, el('b', {}, a.assetTag)), el('td', {}, a.name), el('td', {}, pill(a.status)))))),
          ));
        } }, 'View'));
        return el('tr', {},
          el('td', {}, emp.employeeNumber), el('td', {}, el('b', {}, emp.fullName)), el('td', {}, emp.email || '—'),
          el('td', {}, emp.jobTitle || '—'), el('td', {}, nameOf('departments', emp.departmentId)), el('td', {}, nameOf('branches', emp.branchId)),
          holdCell,
        );
      })),
    ));
  }
  view.append(
    el('div', { class: 'toolbar' },
      el('div', { style: 'flex:1' }),
      el('button', { class: 'btn primary', onclick: () => {
        const form = el('form', { class: 'form-grid' });
        const f = (lbl, node) => field(lbl, node);
        form.append(
          f('Employee number *', input('employeeNumber', { required: true, placeholder: 'EMP-0001' })),
          f('Full name *', input('fullName', { required: true })),
          f('Email', input('email', { type: 'email' })),
          f('Job title', input('jobTitle')),
          f('Department', select('departmentId', refOptions(S.lists.departments || [], (d) => d.name))),
          f('Branch', select('branchId', refOptions(S.lists.branches || [], (b) => b.name))),
        );
        const m = modal('New employee', el('div', {}, form, el('div', { class: 'actions' },
          el('button', { class: 'btn', onclick: () => m.remove() }, 'Cancel'),
          el('button', { class: 'btn primary', onclick: async (e) => {
            e.target.disabled = true;
            try { await api('/employees', { method: 'POST', body: formData(form) }); toast('Employee added'); m.remove(); load(); }
            catch (err) { toast(err.message, true); e.target.disabled = false; }
          } }, 'Add employee'),
        )));
      } }, '＋ New employee'),
    ),
    el('div', { class: 'panel' }, wrap),
  );
  await load();
}

/* ---- licenses ---- */
async function viewLicenses(view) {
  await Promise.all([refList('employees'), refList('suppliers')]);
  const wrap = el('div');
  async function load() {
    const data = await api('/licenses?pageSize=100');
    wrap.innerHTML = '';
    if (!data.items.length) { wrap.append(el('div', { class: 'empty' }, 'No licenses yet.')); return; }
    wrap.append(el('table', { class: 'data' },
      el('thead', {}, el('tr', {}, ['License', 'Vendor', 'Type', 'Seats', 'Expires', ''].map((h) => el('th', {}, h)))),
      el('tbody', {}, data.items.map((lic) => el('tr', {},
        el('td', {}, el('b', {}, lic.name)),
        el('td', {}, lic.vendor || '—'),
        el('td', {}, titleCase(lic.type)),
        el('td', { class: 'num' }, `${lic.seatsUsed} / ${lic.seats} used`),
        el('td', {}, fmtDate(lic.expiryDate)),
        el('td', { class: 'right' }, el('button', { class: 'btn sm', onclick: () => {
          const empSel = select('employeeId', refOptions(S.lists.employees || [], (e2) => e2.fullName, '— pick employee —'));
          const m = modal(`Assign seat — ${lic.name}`, el('div', {},
            el('p', { class: 'muted' }, `${lic.seatsRemaining} seat(s) remaining`),
            field('Employee', empSel),
            el('div', { class: 'actions' },
              el('button', { class: 'btn', onclick: () => m.remove() }, 'Cancel'),
              el('button', { class: 'btn primary', onclick: async (e) => {
                e.target.disabled = true;
                try { await api(`/licenses/${lic.id}/assign`, { method: 'POST', body: { employeeId: empSel.value || undefined } }); toast('Seat assigned'); m.remove(); load(); }
                catch (err) { toast(err.message, true); e.target.disabled = false; }
              } }, 'Assign'),
            ),
          ));
        } }, 'Assign seat')),
      ))),
    ));
  }
  view.append(
    el('div', { class: 'toolbar' }, el('div', { style: 'flex:1' }),
      el('button', { class: 'btn primary', onclick: () => {
        const form = el('form', { class: 'form-grid' });
        form.append(
          field('Name *', input('name', { required: true, placeholder: 'Microsoft 365 E3' })),
          field('Vendor', input('vendor')),
          field('License key', input('licenseKey')),
          field('Seats', input('seats', { type: 'number', min: 1, value: 1 })),
          field('Expiry date', input('expiryDate', { type: 'date' })),
          field('Purchase cost', input('purchaseCost', { type: 'number', step: '0.01', min: 0 })),
        );
        const m = modal('New license', el('div', {}, form, el('div', { class: 'actions' },
          el('button', { class: 'btn', onclick: () => m.remove() }, 'Cancel'),
          el('button', { class: 'btn primary', onclick: async (e) => {
            e.target.disabled = true;
            try {
              const body = formData(form);
              if (body.seats) body.seats = Number(body.seats);
              if (body.purchaseCost) body.purchaseCost = Number(body.purchaseCost);
              await api('/licenses', { method: 'POST', body }); toast('License added'); m.remove(); load();
            } catch (err) { toast(err.message, true); e.target.disabled = false; }
          } }, 'Add license'),
        )));
      } }, '＋ New license')),
    el('div', { class: 'panel' }, wrap),
  );
  await load();
}

/* ---- maintenance ---- */
async function viewMaintenance(view) {
  const wrap = el('div');
  async function load() {
    const data = await api('/maintenance?pageSize=100');
    wrap.innerHTML = '';
    if (!data.items.length) { wrap.append(el('div', { class: 'empty' }, 'No maintenance records yet.')); return; }
    wrap.append(el('table', { class: 'data' },
      el('thead', {}, el('tr', {}, ['Title', 'Type', 'Status', 'Scheduled', 'Cost', ''].map((h) => el('th', {}, h)))),
      el('tbody', {}, data.items.map((rec) => el('tr', {},
        el('td', {}, el('b', {}, rec.title)),
        el('td', {}, titleCase(rec.type)),
        el('td', {}, pill(rec.status)),
        el('td', {}, fmtDate(rec.scheduledFor)),
        el('td', { class: 'num' }, fmtMoney(rec.cost)),
        el('td', { class: 'right' }, ['SCHEDULED', 'IN_PROGRESS'].includes(rec.status)
          ? el('button', { class: 'btn sm', onclick: async () => {
              try {
                const next = rec.status === 'SCHEDULED' ? 'IN_PROGRESS' : 'COMPLETED';
                await api(`/maintenance/${rec.id}`, { method: 'PATCH', body: { status: next } });
                toast(`Marked ${titleCase(next)}`); load();
              } catch (err) { toast(err.message, true); }
            } }, rec.status === 'SCHEDULED' ? 'Start work' : 'Complete')
          : ''),
      ))),
    ));
  }
  view.append(
    el('div', { class: 'toolbar' }, el('div', { style: 'flex:1' }),
      el('button', { class: 'btn primary', onclick: async () => {
        const assets = (await api('/assets?pageSize=200')).items;
        const form = el('form', { class: 'form-grid' });
        form.append(
          field('Asset *', select('assetId', assets.map((a) => ({ value: a.id, label: `${a.assetTag} — ${a.name}` })), { required: true })),
          field('Type *', select('type', ['PREVENTIVE','CORRECTIVE','INSPECTION','UPGRADE','VENDOR_REPAIR','INTERNAL_REPAIR'].map((t) => ({ value: t, label: titleCase(t) })))),
          field('Title *', input('title', { required: true, placeholder: 'Annual service' })),
          field('Scheduled for', input('scheduledFor', { type: 'date' })),
          field('Estimated cost', input('cost', { type: 'number', step: '0.01', min: 0 })),
        );
        const m = modal('Schedule maintenance', el('div', {},
          assets.length === 0 ? el('p', { class: 'muted' }, 'Create an asset first.') : null,
          form,
          el('div', { class: 'actions' },
            el('button', { class: 'btn', onclick: () => m.remove() }, 'Cancel'),
            el('button', { class: 'btn primary', disabled: assets.length === 0 || null, onclick: async (e) => {
              e.target.disabled = true;
              try {
                const body = formData(form);
                if (body.cost) body.cost = Number(body.cost);
                await api('/maintenance', { method: 'POST', body }); toast('Work order created'); m.remove(); load();
              } catch (err) { toast(err.message, true); e.target.disabled = false; }
            } }, 'Create'),
          ),
        ));
      } }, '＋ Schedule work'),
    ),
    el('div', { class: 'panel' }, wrap),
  );
  await load();
}

/* ---- reports ---- */
async function viewReports(view) {
  const reports = [
    ['asset-inventory', 'Asset Inventory', 'Every asset with specs, status, cost and warranty'],
    ['warranty', 'Warranty Report', 'Expired and expiring warranties (next 180 days)'],
    ['assignments', 'Employee Assets', 'Check-out history with overdue flags'],
    ['licenses', 'Software Licenses', 'Seats, costs, expiry and renewals'],
    ['maintenance', 'Maintenance', 'All work orders with costs'],
    ['financial', 'Financial / Depreciation', 'Purchase costs and current book values'],
  ];
  async function download(type, format) {
    try {
      const blob = await api(`/reports/${type}?format=${format}`);
      const a = el('a', { href: URL.createObjectURL(blob), download: `${type}.${format}` });
      document.body.append(a); a.click(); a.remove();
      toast('Report downloaded');
    } catch (err) { toast(err.message, true); }
  }
  view.append(el('div', { class: 'panel' },
    el('h3', {}, 'Generate reports'),
    reports.map(([type, name, desc]) => el('div', { class: 'report-card' },
      el('div', {}, el('b', {}, name), el('div', { class: 'muted', style: 'font-size:12.5px' }, desc)),
      el('div', { class: 'chips' }, ['xlsx', 'pdf', 'csv'].map((fmt) =>
        el('button', { class: 'btn sm', onclick: () => download(type, fmt) }, fmt.toUpperCase()),
      )),
    )),
  ));
}

/* ---- organization structure ---- */
async function viewStructure(view) {
  const sections = [
    ['branches', 'Branches', [['name', 'Name *', { required: true }], ['code', 'Code *', { required: true, placeholder: 'HQ' }], ['city', 'City', {}]]],
    ['departments', 'Departments', [['name', 'Name *', { required: true }], ['code', 'Code *', { required: true, placeholder: 'FIN' }]]],
    ['categories', 'Asset categories', [['name', 'Name *', { required: true, placeholder: 'Laptops' }], ['code', 'Code *', { required: true, placeholder: 'LAP' }]]],
    ['suppliers', 'Suppliers', [['name', 'Name *', { required: true }], ['email', 'Email', { type: 'email' }]]],
  ];
  for (const [kind, label, fields] of sections) {
    const wrap = el('div');
    const panel = el('div', { class: 'panel' }, el('h3', {}, label), wrap);
    view.append(panel);
    const load = async () => {
      S.lists[kind] = null;
      const items = await refList(kind);
      wrap.innerHTML = '';
      const form = el('form', { class: 'flex', style: 'flex-wrap:wrap;margin-bottom:10px', onsubmit: async (e) => {
        e.preventDefault();
        try { await api('/' + kind, { method: 'POST', body: formData(form) }); toast('Added'); load(); }
        catch (err) { toast(err.message, true); }
      } });
      for (const [name, ph, attrs] of fields) form.append(input(name, { placeholder: ph.replace(' *', ''), ...attrs, style: 'padding:8px 11px;border:1px solid var(--baseline);border-radius:8px;background:var(--surface)' }));
      form.append(el('button', { class: 'btn primary sm', type: 'submit' }, 'Add'));
      wrap.append(form);
      if (!items.length) { wrap.append(el('div', { class: 'muted' }, 'None yet — add the first one above.')); continueLoad(); return; }
      wrap.append(el('table', { class: 'data' }, el('tbody', {}, items.map((item) => el('tr', {},
        el('td', {}, el('b', {}, item.name)),
        el('td', { class: 'muted' }, item.code || item.email || item.city || ''),
        el('td', { class: 'right' }, el('button', { class: 'btn sm danger', onclick: async () => {
          if (!confirm(`Delete ${item.name}?`)) return;
          try { await api(`/${kind}/${item.id}`, { method: 'DELETE' }); toast('Deleted'); load(); }
          catch (err) { toast(err.message, true); }
        } }, 'Delete')),
      )))));
      function continueLoad() {}
    };
    await load();
  }
}

/* ---- audit trail ---- */
async function viewAudit(view) {
  const data = await api('/audit-logs?pageSize=50');
  view.append(el('div', { class: 'panel' },
    el('h3', {}, 'Audit trail (latest 50 actions)'),
    data.items.length === 0 ? el('div', { class: 'empty' }, 'No entries yet') :
      el('table', { class: 'data' },
        el('thead', {}, el('tr', {}, ['When', 'Who', 'Action', 'Entity'].map((h) => el('th', {}, h)))),
        el('tbody', {}, data.items.map((log) => el('tr', {},
          el('td', {}, fmtDateTime(log.createdAt)),
          el('td', {}, log.actorEmail || 'system'),
          el('td', {}, el('b', {}, log.action)),
          el('td', { class: 'muted' }, log.entityType || ''),
        ))),
      ),
  ));
}

/* ── router ─────────────────────────────────────────────────────── */
const ROUTES = {
  '#/dashboard': ['Dashboard', viewDashboard],
  '#/assets': ['Assets', viewAssets],
  '#/employees': ['Employees', viewEmployees],
  '#/licenses': ['Software Licenses', viewLicenses],
  '#/maintenance': ['Maintenance', viewMaintenance],
  '#/reports': ['Reports', viewReports],
  '#/structure': ['Organization', viewStructure],
  '#/audit': ['Audit Trail', viewAudit],
};

async function render() {
  document.querySelectorAll('.overlay').forEach((o) => o.remove()); // no stale modals across navigation
  if (!S.token) { renderAuth(); return; }
  const route = ROUTES[location.hash] ? location.hash : '#/dashboard';
  const { view, title } = renderApp();
  document.querySelectorAll('[data-nav]').forEach((a) => a.classList.toggle('active', a.getAttribute('data-nav') === route));
  const [pageTitle, viewFn] = ROUTES[route];
  title.textContent = pageTitle;
  view.append(el('div', { class: 'muted' }, 'Loading…'));
  try {
    view.innerHTML = '';
    await viewFn(view);
  } catch (err) {
    view.innerHTML = '';
    view.append(el('div', { class: 'panel' }, el('div', { class: 'empty' }, err.message)));
  }
}

window.addEventListener('hashchange', render);
render();
