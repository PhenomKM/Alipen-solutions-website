(() => {
  const API = '/api/admin';
  const state = {
    csrfToken: '', page: 1, pageSize: 20, total: 0, search: '', status: 'all', dateFrom: '', dateTo: '', followUp: 'all', currentReference: '', isPrimary: false, username: '',
    quoteDialogScrollY: 0, quoteDialogOriginalStyle: null, quoteDialogOriginalStyleCaptured: false,
    quoteDialogViewport: null, quoteDialogViewportSync: null
  };
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
    if (status === 'won') return 'Won';
    if (status === 'lost') return 'Lost';
    return status;
  }

  function statusClass(status) {
    if (status === 'in_progress' || status === 'completed' || status === 'won' || status === 'lost') return status;
    if (!status || status === 'received' || status === 'new') return 'new';
    return 'other';
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Africa/Nairobi' }).format(date);
  }

  function nairobiToday() {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Nairobi', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function followUpLabel(date) {
    if (!date) return '';
    if (date < nairobiToday()) return 'Overdue';
    if (date === nairobiToday()) return 'Due today';
    return 'Upcoming';
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
    const quickStatus = document.createElement('select');
    quickStatus.className = 'row-status-select';
    quickStatus.setAttribute('aria-label', `Update status for ${quote.reference}`);
    [['received', 'New'], ['in_progress', 'In progress'], ['completed', 'Completed'], ['won', 'Won'], ['lost', 'Lost']].forEach(([value, label]) => {
      const option = makeElement('option', '', label);
      option.value = value;
      quickStatus.append(option);
    });
    quickStatus.value = ['received', 'new', 'in_progress', 'completed', 'won', 'lost'].includes(quote.status)
      ? (quote.status === 'new' ? 'received' : quote.status)
      : 'received';
    quickStatus.addEventListener('change', async () => {
      const previousStatus = ['received', 'new', 'in_progress', 'completed', 'won', 'lost'].includes(quote.status)
        ? (quote.status === 'new' ? 'received' : quote.status)
        : 'received';
      quickStatus.disabled = true;
      try {
        await api(`/quotes/${encodeURIComponent(quote.reference)}/status`, { method: 'PATCH', body: JSON.stringify({ status: quickStatus.value }) });
        showNotice('Quote status updated.');
        await Promise.all([loadOverview(), loadQuotes()]);
      } catch (error) {
        quickStatus.value = previousStatus;
        showNotice(error.message, true);
      } finally { quickStatus.disabled = false; }
    });
    actionCell.append(quickStatus);
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
    byId('wonCount').textContent = data.won || 0;
    byId('followUpCount').textContent = data.follow_up_due || 0;
    renderRecent(data.recent || []);
    renderAttention(data.attention || []);
    renderFollowUps(data.follow_ups || []);
  }

  function renderAttention(quotes) {
    const host = byId('attentionRows');
    host.replaceChildren();
    byId('attentionEmpty').hidden = quotes.length > 0;
    quotes.forEach((quote) => host.append(makeReminderRow(quote, false)));
  }

  function makeReminderRow(quote, withReminder) {
    const row = makeElement('article', 'reminder-row');
    const main = makeElement('div', 'reminder-main');
    const title = makeElement('button', 'reference-link', `${quote.reference} · ${quote.name}`);
    title.type = 'button';
    title.addEventListener('click', () => openQuote(quote.reference));
    main.append(title);
    main.append(makeElement('span', '', `${quote.facility || ''} · ${displayStatus(quote.status)}`));
    if (withReminder) {
      const flag = makeElement('span', `reminder-flag ${followUpLabel(quote.follow_up_date).toLowerCase().replace(' ', '-')}`, `${followUpLabel(quote.follow_up_date)} · ${quote.follow_up_date}`);
      main.append(flag);
      if (quote.follow_up_note) main.append(makeElement('span', 'reminder-note', quote.follow_up_note));
    } else if (quote.follow_up_date && !quote.follow_up_completed && quote.follow_up_date <= nairobiToday()) {
      main.append(makeElement('span', 'reminder-flag overdue', `Follow-up ${followUpLabel(quote.follow_up_date).toLowerCase()}`));
    }
    row.append(main);
    if (withReminder) {
      const complete = makeElement('button', 'admin-button reminder-complete', 'Mark complete');
      complete.type = 'button';
      complete.addEventListener('click', async () => {
        complete.disabled = true;
        try {
          await api(`/follow-ups/${encodeURIComponent(quote.reference)}`, { method: 'PATCH', body: JSON.stringify({ completed: true }) });
          await loadOverview();
        } catch (error) { showNotice(error.message, true); complete.disabled = false; }
      });
      row.append(complete);
    }
    return row;
  }

  function renderFollowUps(quotes) {
    const host = byId('followUpRows');
    host.replaceChildren();
    byId('followUpsEmpty').hidden = quotes.length > 0;
    quotes.forEach((quote) => host.append(makeReminderRow(quote, true)));
  }

  async function loadQuotes() {
    clearNotice();
    const query = new URLSearchParams({ page: String(state.page), search: state.search, status: state.status, follow_up: state.followUp });
    if (state.dateFrom) query.set('date_from', state.dateFrom);
    if (state.dateTo) query.set('date_to', state.dateTo);
    const data = await api(`/quotes?${query.toString()}`);
    state.total = data.total;
    const maxPage = Math.max(1, Math.ceil(state.total / state.pageSize));
    if (state.page > maxPage) {
      state.page = maxPage;
      return loadQuotes();
    }
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

  async function loadAdminUsers() {
    if (!state.isPrimary) throw new Error('Primary administrator access required.');
    const data = await api('/users');
    const tbody = byId('adminUsersRows');
    const users = data.users || [];
    tbody.replaceChildren();
    byId('adminUsersEmpty').hidden = users.length > 0;
    users.forEach((user) => {
      const row = document.createElement('tr');
      const nameCell = makeElement('td', 'customer-cell');
      nameCell.append(makeElement('strong', '', user.username));
      row.append(nameCell);
      const date = user.created_at ? formatDate(user.created_at) : '—';
      const dateCell = makeElement('td', '', date);
      row.append(dateCell);
      const statusCell = document.createElement('td');
      statusCell.append(makeElement('span', `status-pill ${user.is_active ? 'completed' : 'other'}`, user.is_active ? 'Active' : 'Deactivated'));
      row.append(statusCell);
      const actionCell = document.createElement('td');
      const edit = makeElement('button', 'text-button', 'Manage');
      edit.type = 'button';
      edit.addEventListener('click', () => openAdminUserEditor(user));
      actionCell.append(edit);
      row.append(actionCell);
      tbody.append(row);
    });
  }

  async function loadPrivateNotes(reference) {
    const data = await api(`/quotes/${encodeURIComponent(reference)}/notes`);
    const host = byId('privateNotesList');
    host.replaceChildren();
    (data.notes || []).forEach((note) => {
      const card = makeElement('article', 'private-note');
      const header = makeElement('div', 'private-note-header');
      header.append(makeElement('strong', '', note.author));
      header.append(makeElement('time', '', formatDate(note.created_at)));
      if (note.updated_at && note.updated_at !== note.created_at) {
        header.append(makeElement('time', '', `Edited ${formatDate(note.updated_at)}`));
      }
      card.append(header);
      card.append(makeElement('p', '', note.content));
      if (state.isPrimary || note.author === state.username) {
        const actions = makeElement('div', 'private-note-actions');
        const edit = makeElement('button', 'text-button', 'Edit');
        edit.type = 'button';
        edit.addEventListener('click', async () => {
          const updated = window.prompt('Edit private note', note.content);
          if (updated === null) return;
          try {
            await api(`/notes/${encodeURIComponent(note.id)}`, { method: 'PATCH', body: JSON.stringify({ content: updated }) });
            await loadPrivateNotes(reference);
          } catch (error) { showNotice(error.message, true); }
        });
        const remove = makeElement('button', 'text-button danger-text', 'Delete');
        remove.type = 'button';
        remove.addEventListener('click', async () => {
          if (!window.confirm('Delete this private note?')) return;
          try {
            await api(`/notes/${encodeURIComponent(note.id)}`, { method: 'DELETE' });
            await loadPrivateNotes(reference);
          } catch (error) { showNotice(error.message, true); }
        });
        actions.append(edit, remove);
        card.append(actions);
      }
      host.append(card);
    });
    if (!data.notes || !data.notes.length) host.append(makeElement('p', 'empty-note', 'No private notes yet.'));
  }

  function syncQuoteDialogToVisualViewport(dialog) {
    const viewport = window.visualViewport;
    if (!viewport) return;
    dialog.style.position = 'fixed';
    dialog.style.inset = 'auto';
    dialog.style.left = `${viewport.offsetLeft}px`;
    dialog.style.top = `${viewport.offsetTop}px`;
    dialog.style.right = 'auto';
    dialog.style.bottom = 'auto';
    dialog.style.width = `${viewport.width}px`;
    dialog.style.height = `${viewport.height}px`;
    dialog.style.maxWidth = 'none';
    dialog.style.maxHeight = 'none';
    dialog.style.margin = '0';
    dialog.style.transform = 'none';
    dialog.style.boxSizing = 'border-box';
  }

  function prepareQuoteDialogViewport(dialog) {
    const viewport = window.visualViewport;
    const isMobileViewport = window.matchMedia('(max-width: 720px)').matches || (viewport && viewport.width <= 720);
    if (!viewport || !isMobileViewport) return;

    state.quoteDialogOriginalStyle = dialog.getAttribute('style');
    state.quoteDialogOriginalStyleCaptured = true;
    state.quoteDialogViewport = viewport;
    state.quoteDialogViewportSync = () => syncQuoteDialogToVisualViewport(dialog);
    viewport.addEventListener('resize', state.quoteDialogViewportSync);
    viewport.addEventListener('scroll', state.quoteDialogViewportSync);
    window.addEventListener('resize', state.quoteDialogViewportSync);
    state.quoteDialogViewportSync();
  }

  function restoreQuoteDialogViewport(dialog) {
    if (!state.quoteDialogOriginalStyleCaptured) return;
    if (state.quoteDialogViewport && state.quoteDialogViewportSync) {
      state.quoteDialogViewport.removeEventListener('resize', state.quoteDialogViewportSync);
      state.quoteDialogViewport.removeEventListener('scroll', state.quoteDialogViewportSync);
      window.removeEventListener('resize', state.quoteDialogViewportSync);
    }
    if (state.quoteDialogOriginalStyle === null) dialog.removeAttribute('style');
    else if (state.quoteDialogOriginalStyle !== null) dialog.setAttribute('style', state.quoteDialogOriginalStyle);
    state.quoteDialogOriginalStyle = null;
    state.quoteDialogOriginalStyleCaptured = false;
    state.quoteDialogViewport = null;
    state.quoteDialogViewportSync = null;
  }

  function openAdminUserEditor(user) {
    if (!state.isPrimary) return;
    const form = byId('editAdminUserForm');
    form.elements.namedItem('id').value = user.id;
    form.elements.namedItem('username').value = user.username;
    form.elements.namedItem('password').value = '';
    form.elements.namedItem('is_active').checked = Boolean(user.is_active);
    byId('adminUserDialog').showModal();
  }

  function showView(name) {
    if (name === 'users' && !state.isPrimary) return;
    const overview = name === 'overview';
    byId('overviewView').hidden = name !== 'overview';
    byId('quotesView').hidden = name !== 'quotes';
    byId('documentsView').hidden = name !== 'documents';
    byId('usersView').hidden = name !== 'users';
    document.querySelectorAll('[data-admin-view]').forEach((button) => {
      button.classList.toggle('active', button.dataset.adminView === name);
    });
    byId('adminSidebar').classList.remove('open');
    byId('sidebarToggle').setAttribute('aria-expanded', 'false');
    if (overview) loadOverview().catch((error) => showNotice(error.message, true));
    else if (name === 'quotes') loadQuotes().catch((error) => showNotice(error.message, true));
    else if (name === 'users') loadAdminUsers().catch((error) => showNotice(error.message, true));
  }

  async function openQuote(reference) {
    clearNotice();
    state.currentReference = reference;
    const dialog = byId('quoteDetailDialog');
    byId('detailLoading').hidden = false;
    byId('detailContent').hidden = true;
    state.quoteDialogScrollY = window.scrollY;
    try {
      prepareQuoteDialogViewport(dialog);
      dialog.showModal();
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
      byId('followUpDate').value = quote.follow_up_date || '';
      byId('followUpNote').value = quote.follow_up_note || '';
      byId('followUpCompleted').checked = Boolean(quote.follow_up_completed);
      const itemList = byId('detailItems');
      itemList.replaceChildren();
      const items = Array.isArray(quote.items) ? quote.items : [];
      if (items.length) {
        items.forEach((item) => itemList.append(makeElement('li', '', `${item.name || 'Medical product'} — Qty: ${item.quantity || 1}`)));
      } else {
        itemList.append(makeElement('li', '', 'General catalogue and procurement inquiry'));
      }
      byId('detailStatus').value = ['received', 'new', 'in_progress', 'completed', 'won', 'lost'].includes(quote.status) ? (quote.status === 'new' ? 'received' : quote.status) : 'received';
      await loadPrivateNotes(quote.reference);
      byId('detailLoading').hidden = true;
      byId('detailContent').hidden = false;
    } catch (error) {
      if (dialog.open) dialog.close();
      else restoreQuoteDialogViewport(dialog);
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
      state.isPrimary = Boolean(session.isPrimary);
      state.username = session.username;
      byId('adminUsersNav').hidden = !state.isPrimary;
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
    document.querySelectorAll('[data-open-due]').forEach((button) => button.addEventListener('click', () => {
      state.followUp = 'due';
      byId('followUpFilter').checked = true;
      state.page = 1;
      showView('quotes');
    }));
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
    const applyDateFilters = () => {
      state.dateFrom = byId('dateFromFilter').value;
      state.dateTo = byId('dateToFilter').value;
      state.page = 1;
      loadQuotes().catch((error) => showNotice(error.message, true));
    };
    byId('dateFromFilter').addEventListener('change', applyDateFilters);
    byId('dateToFilter').addEventListener('change', applyDateFilters);
    byId('followUpFilter').addEventListener('change', () => {
      state.followUp = byId('followUpFilter').checked ? 'due' : 'all';
      state.page = 1;
      loadQuotes().catch((error) => showNotice(error.message, true));
    });
    byId('followUpDate').addEventListener('change', () => {
      byId('followUpCompleted').checked = false;
    });
    byId('clearFilters').addEventListener('click', () => {
      state.search = '';
      state.status = 'all';
      state.dateFrom = '';
      state.dateTo = '';
      state.followUp = 'all';
      state.page = 1;
      byId('quoteSearch').value = '';
      byId('statusFilter').value = 'all';
      byId('dateFromFilter').value = '';
      byId('dateToFilter').value = '';
      byId('followUpFilter').checked = false;
      loadQuotes().catch((error) => showNotice(error.message, true));
    });
    byId('previousPage').addEventListener('click', () => {
      if (state.page > 1) { state.page -= 1; loadQuotes().catch((error) => showNotice(error.message, true)); }
    });
    byId('nextPage').addEventListener('click', () => {
      if (state.page * state.pageSize < state.total) { state.page += 1; loadQuotes().catch((error) => showNotice(error.message, true)); }
    });
    byId('closeDetail').addEventListener('click', () => byId('quoteDetailDialog').close());
    const quoteDialog = byId('quoteDetailDialog');
    quoteDialog.addEventListener('click', (event) => {
      if (event.target === quoteDialog) quoteDialog.close();
    });
    quoteDialog.addEventListener('close', () => {
      restoreQuoteDialogViewport(quoteDialog);
      window.requestAnimationFrame(() => window.scrollTo(0, state.quoteDialogScrollY));
    });
    byId('privateNoteForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const input = byId('privateNoteInput');
      try {
        await api(`/quotes/${encodeURIComponent(state.currentReference)}/notes`, { method: 'POST', body: JSON.stringify({ content: input.value }) });
        input.value = '';
        await loadPrivateNotes(state.currentReference);
        showNotice('Private note saved.');
      } catch (error) { showNotice(error.message, true); }
    });
    byId('saveFollowUp').addEventListener('click', async () => {
      const date = byId('followUpDate').value;
      const completed = byId('followUpCompleted').checked;
      if (!date && !completed) { showNotice('Choose a follow-up date or mark the reminder complete.', true); return; }
      try {
        await api(`/follow-ups/${encodeURIComponent(state.currentReference)}`, {
          method: 'PATCH', body: JSON.stringify({ date: date || null, note: byId('followUpNote').value, completed })
        });
        showNotice('Follow-up reminder saved.');
        await loadOverview();
        await loadQuotes();
      } catch (error) { showNotice(error.message, true); }
    });
    if (state.isPrimary) {
      byId('createAdminUserForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const button = byId('createAdminUserButton');
        const formData = new FormData(form);
        button.disabled = true;
        try {
          await api('/users', {
            method: 'POST',
            body: JSON.stringify({ username: formData.get('username'), password: formData.get('password') })
          });
          form.reset();
          showNotice('Administrator account created.');
          await loadAdminUsers();
        } catch (error) {
          showNotice(error.message, true);
        } finally {
          button.disabled = false;
        }
      });
      byId('closeAdminUserDialog').addEventListener('click', () => byId('adminUserDialog').close());
      byId('cancelAdminUserEdit').addEventListener('click', () => byId('adminUserDialog').close());
      byId('editAdminUserForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const formData = new FormData(form);
        const activeCheckbox = form.elements.namedItem('is_active');
        const button = byId('saveAdminUserButton');
        const update = {
          username: formData.get('username'),
          is_active: activeCheckbox.checked,
        };
        const newPassword = formData.get('password');
        if (newPassword) update.password = newPassword;
        button.disabled = true;
        try {
          await api(`/users/${encodeURIComponent(formData.get('id'))}`, {
            method: 'PATCH',
            body: JSON.stringify(update)
          });
          byId('adminUserDialog').close();
          form.reset();
          showNotice('Administrator account updated. Any existing sessions for that account were signed out.');
          await loadAdminUsers();
        } catch (error) {
          showNotice(error.message, true);
        } finally {
          button.disabled = false;
        }
      });
    }
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
