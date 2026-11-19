(() => {
  const API = '/api/admin';
  const state = { csrfToken: '', page: 1, pageSize: 20, total: 0, search: '', status: 'all', currentReference: '' };
  const byId = (id) => document.getElementById(id);

  function makeElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function showNotice(message, isError = false) {
    const notice = byId('adminNotice');
    if (!notice) return;
    notice.textContent = message;
    notice.classList.toggle('error', isError);
    notice.hidden = false;
  }

  function clearNotice() {
    const notice = byId('adminNotice');
    if (notice) notice.hidden = true;
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    if (options.method && options.method !== 'GET' && state.csrfToken) {
      headers.set('X-CSRF-Token', state.csrfToken);
    }
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers,
      credentials: 'same-origin',
      cache: 'no-store'
    });
    let result;
    try {
      result = await response.json();
    } catch (_) {
      throw new Error('The server returned an unreadable response. Please try again.');
    }
    if (response.status === 401 && document.body.dataset.adminPage === 'dashboard') {
      window.location.assign('/admin/login');
    }
    if (!response.ok) throw new Error(result.message || 'The request could not be completed.');
    return result;
  }

  function displayStatus(status) {
    if (!status || status === 'received' || status === 'new') return 'New';
    if (status === 'in_progress') return 'In progress';
    if (status === 'completed') return 'Completed';
    return status;
  }

  function statusClass(status) {
    if (status === 'in_progress' || status === 'completed') return status;
    if (!status || status === 'received' || status === 'new') return 'new';
    return 'other';
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
  }

  function addCell(row, value, className) {
    const cell = makeElement('td', className, value || '—');
    row.append(cell);
    return cell;
  }

  function appendQuoteRow(tbody, quote) {
    const row = document.createElement('tr');
    const refCell = document.createElement('td');
    const open = makeElement('button', 'reference-link', quote.reference);
    open.type = 'button';
    open.addEventListener('click', () => openQuote(quote.reference));
    refCell.append(open);
    row.append(refCell);

    const customer = makeElement('td', 'customer-cell');
    customer.append(makeElement('strong', '', quote.name));
    customer.append(makeElement('span', '', quote.email));
    row.append(customer);
    addCell(row, quote.facility);
    addCell(row, quote.county);
    const statusCell = document.createElement('td');
    statusCell.append(makeElement('span', `status-pill ${statusClass(quote.status)}`, displayStatus(quote.status)));
    row.append(statusCell);
    addCell(row, formatDate(quote.created_at));
    const actionCell = document.createElement('td');
    const detailsButton = makeElement('button', 'text-button', 'Details');
    detailsButton.type = 'button';
    detailsButton.addEventListener('click', () => openQuote(quote.reference));
    actionCell.append(detailsButton);
    row.append(actionCell);
    tbody.append(row);
  }

  function renderRecent(quotes) {
    const tbody = byId('recentRows');
    const empty = byId('recentEmpty');
    tbody.replaceChildren();
    empty.hidden = quotes.length > 0;
    quotes.forEach((quote) => appendQuoteRow(tbody, quote));
  }

  async function loadOverview() {
    const data = await api('/overview');
    byId('totalCount').textContent = data.total;
    byId('newCount').textContent = data.new;
    byId('progressCount').textContent = data.in_progress;
    byId('completedCount').textContent = data.completed;
    renderRecent(data.recent || []);
  }

  async function loadQuotes() {
    clearNotice();
    const query = new URLSearchParams({ page: String(state.page), search: state.search, status: state.status });
    const data = await api(`/quotes?${query.toString()}`);
    state.total = data.total;
    const tbody = byId('quoteRows');
    tbody.replaceChildren();
    (data.items || []).forEach((quote) => appendQuoteRow(tbody, quote));
    byId('quotesEmpty').hidden = data.items.length > 0;
    const first = state.total ? ((state.page - 1) * state.pageSize) + 1 : 0;
    const last = Math.min(state.page * state.pageSize, state.total);
    byId('pageSummary').textContent = `Showing ${first}–${last} of ${state.total} requests`;
    byId('previousPage').disabled = state.page <= 1;
    byId('nextPage').disabled = last >= state.total;
  }

  function showView(name) {
    const overview = name === 'overview';
    byId('overviewView').hidden = !overview;
    byId('quotesView').hidden = overview;
    document.querySelectorAll('[data-admin-view]').forEach((button) => {
      button.classList.toggle('active', button.dataset.adminView === name);
    });
    byId('adminSidebar').classList.remove('open');
    byId('sidebarToggle').setAttribute('aria-expanded', 'false');
    if (overview) loadOverview().catch((error) => showNotice(error.message, true));
    else loadQuotes().catch((error) => showNotice(error.message, true));
  }

  async function openQuote(reference) {
    clearNotice();
    state.currentReference = reference;
    const dialog = byId('quoteDetailDialog');
    byId('detailLoading').hidden = false;
    byId('detailContent').hidden = true;
    dialog.showModal();
    try {
      const quote = await api(`/quotes/${encodeURIComponent(reference)}`);
      byId('detailReference').textContent = quote.reference;
      byId('detailStatusBadge').replaceChildren(makeElement('span', `status-pill ${statusClass(quote.status)}`, displayStatus(quote.status)));
      byId('detailName').textContent = quote.name || '—';
      byId('detailFacility').textContent = quote.facility || '—';
      byId('detailFacilityType').textContent = quote.facility_type || '—';
      byId('detailCounty').textContent = quote.county || '—';
      byId('detailPhone').textContent = quote.phone || '—';
      byId('detailEmail').textContent = quote.email || '—';
      byId('detailDate').textContent = formatDate(quote.created_at);
      byId('detailRequirements').textContent = quote.requirements || 'No additional requirements provided.';
      const itemList = byId('detailItems');
      itemList.replaceChildren();
      const items = Array.isArray(quote.items) ? quote.items : [];
      if (items.length) {
        items.forEach((item) => itemList.append(makeElement('li', '', `${item.name || 'Medical product'} — Qty: ${item.quantity || 1}`)));
      } else {
        itemList.append(makeElement('li', '', 'General catalogue and procurement inquiry'));
      }
      byId('detailStatus').value = ['received', 'new', 'in_progress', 'completed'].includes(quote.status) ? (quote.status === 'new' ? 'received' : quote.status) : 'received';
      byId('detailLoading').hidden = true;
      byId('detailContent').hidden = false;
    } catch (error) {
      dialog.close();
      showNotice(error.message, true);
    }
  }

  function initLogin() {
    const form = byId('adminLoginForm');
    if (!form) return;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = byId('loginButton');
      const error = byId('loginError');
      error.hidden = true;
      button.disabled = true;
      button.textContent = 'Signing in…';
      const formData = new FormData(form);
      try {
        await api('/login', {
          method: 'POST',
          body: JSON.stringify({ username: formData.get('username'), password: formData.get('password') })
        });
        form.reset();
        window.location.assign('/admin');
      } catch (exception) {
        error.textContent = exception.message;
        error.hidden = false;
      } finally {
        button.disabled = false;
        button.textContent = 'Sign in securely';
      }
    });
  }

  async function initDashboard() {
    try {
      const session = await api('/session');
      state.csrfToken = session.csrfToken;
      byId('adminUsernameLabel').textContent = session.username;
      await loadOverview();
    } catch (error) {
      if (error.message) showNotice(error.message, true);
      return;
    }

    document.querySelectorAll('[data-admin-view]').forEach((button) => {
      button.addEventListener('click', () => showView(button.dataset.adminView));
    });
    document.querySelectorAll('[data-open-quotes]').forEach((button) => button.addEventListener('click', () => showView('quotes')));
    byId('sidebarToggle').addEventListener('click', () => {
      const sidebar = byId('adminSidebar');
      const open = sidebar.classList.toggle('open');
      byId('sidebarToggle').setAttribute('aria-expanded', String(open));
    });

    byId('quoteSearch').addEventListener('input', () => {
      clearTimeout(window.adminSearchTimer);
      window.adminSearchTimer = setTimeout(() => {
        state.search = byId('quoteSearch').value.trim().slice(0, 120);
        state.page = 1;
        loadQuotes().catch((error) => showNotice(error.message, true));
      }, 250);
    });
    byId('statusFilter').addEventListener('change', () => {
      state.status = byId('statusFilter').value;
      state.page = 1;
      loadQuotes().catch((error) => showNotice(error.message, true));
    });
    byId('previousPage').addEventListener('click', () => {
      if (state.page > 1) { state.page -= 1; loadQuotes().catch((error) => showNotice(error.message, true)); }
    });
    byId('nextPage').addEventListener('click', () => {
      if (state.page * state.pageSize < state.total) { state.page += 1; loadQuotes().catch((error) => showNotice(error.message, true)); }
    });
    byId('closeDetail').addEventListener('click', () => byId('quoteDetailDialog').close());
    byId('quoteDetailDialog').addEventListener('click', (event) => {
      if (event.target === byId('quoteDetailDialog')) byId('quoteDetailDialog').close();
    });
    byId('statusForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = byId('saveStatus');
      button.disabled = true;
      try {
        await api(`/quotes/${encodeURIComponent(state.currentReference)}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ status: byId('detailStatus').value })
        });
        byId('quoteDetailDialog').close();
        showNotice('Quote status updated.');
        await Promise.all([loadOverview(), loadQuotes()]);
      } catch (error) {
        showNotice(error.message, true);
      } finally {
        button.disabled = false;
      }
    });
    byId('logoutButton').addEventListener('click', async () => {
      try { await api('/logout', { method: 'POST', body: '{}' }); }
      catch (_) { /* The session may already have expired. */ }
      state.csrfToken = '';
      window.location.assign('/admin/login');
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.adminPage === 'login') initLogin();
    if (document.body.dataset.adminPage === 'dashboard') initDashboard();
  });
})();
