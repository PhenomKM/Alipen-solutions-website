(() => {
  const API = '/api/admin';
  const state = {
    csrfToken: '', page: 1, pageSize: 20, total: 0, search: '', status: 'new', allQuotes: false, dateFrom: '', dateTo: '', followUp: 'all', currentReference: '', isPrimary: false, username: '',
    quoteDialogScrollY: 0, quoteDialogOriginalStyle: null, quoteDialogOriginalStyleCaptured: false,
    quoteDialogViewport: null, quoteDialogViewportSync: null,
    currentQuote: null, invoiceStatus: 'new', invoicePage: 1, invoicePageSize: 20,
    invoiceTotal: 0, invoiceSearch: '', invoiceSearchTimer: null, invoiceProducts: [], invoiceEditing: null
  };
  const byId = (id) => document.getElementById(id);

  function setText(id, value) {
    const node = byId(id);
    if (!node) {
      const error = new Error(`Admin page is missing required element #${id}.`);
      console.error('[Alipen admin] Unable to render text', error);
      showNotice(error.message, true);
      return false;
    }
    node.textContent = value === undefined || value === null ? '' : String(value);
    return true;
  }

  function setValue(id, value) {
    const node = byId(id);
    if (!node) {
      const error = new Error(`Admin page is missing required value control #${id}.`);
      console.error('[Alipen admin] Required form control is missing', error);
      throw error;
    }
    node.value = value === undefined || value === null ? '' : String(value);
  }

  function bind(id, eventName, handler) {
    const node = byId(id);
    if (!node) {
      const error = new Error(`Admin page is missing control #${id}; that control was not initialized.`);
      console.error('[Alipen admin] Unable to initialize control', error);
      showNotice(error.message, true);
      return null;
    }
    node.addEventListener(eventName, handler);
    return node;
  }

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
    if (status === 'won') return 'Completed';
    if (status === 'lost') return 'Lost';
    return status;
  }

  function statusClass(status) {
    if (status === 'won') return 'completed';
    if (status === 'in_progress' || status === 'completed' || status === 'lost') return status;
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
    // Render each dashboard component independently so one stale or incomplete
    // markup fragment cannot prevent the rest of the portal from working.
    [
      ['total requests', () => setText('totalCount', data.total)],
      ['new requests', () => setText('newCount', data.new)],
      ['in progress requests', () => setText('progressCount', data.in_progress)],
      ['completed orders', () => setText('completedCount', data.completed || 0)],
      ['lost requests', () => setText('lostCount', data.lost || 0)],
      ['unpaid invoices', () => setText('unpaidInvoiceCount', data.unpaid_invoices || 0)],
      ['paid invoices', () => setText('paidInvoiceCount', data.paid_invoices || 0)],
      ['due follow-ups', () => setText('followUpCount', data.follow_up_due || 0)],
      ['recent requests', () => renderRecent(data.recent || [])],
      ['attention list', () => renderAttention(data.attention || [])],
      ['follow-up list', () => renderFollowUps(data.follow_ups || [])]
    ].forEach(([component, render]) => {
      try { render(); }
      catch (error) {
        console.error(`[Alipen admin] Failed to render ${component}`, error);
        showNotice(`Could not load the ${component} dashboard component. ${error.message || ''}`.trim(), true);
      }
    });
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
    const query = new URLSearchParams({ page: String(state.page), search: state.search, status: state.allQuotes ? 'all' : state.status, follow_up: state.followUp });
    if (state.dateFrom) query.set('date_from', state.dateFrom);
    if (state.dateTo) query.set('date_to', state.dateTo);
    const data = await api(`/quotes?${query.toString()}`);
    const counts = data.statusCounts || {};
    [['new', 'quoteCountNew'], ['in_progress', 'quoteCountProgress'], ['completed', 'quoteCountCompleted'], ['lost', 'quoteCountLost']].forEach(([key, id]) => setText(id, counts[key] || 0));
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
    setText('pageSummary', `Showing ${first}–${last} of ${state.total} requests`);
    byId('previousPage').disabled = state.page <= 1;
    byId('nextPage').disabled = last >= state.total;
    document.querySelectorAll('[data-quote-status]').forEach((tab) => {
      const active = tab.dataset.quoteStatus === state.status;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
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

  function invoiceCents(value) {
    const match = String(value ?? '0').trim().match(/^(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) return 0n;
    return BigInt(match[1]) * 100n + BigInt((match[2] || '').padEnd(2, '0'));
  }

  function invoiceMoneyCents(cents, currency = 'KES') {
    const safeCents = cents < 0n ? 0n : cents;
    const whole = safeCents / 100n;
    const fraction = String(safeCents % 100n).padStart(2, '0');
    return `${currency} ${whole.toLocaleString()}${fraction === '00' ? '.00' : `.${fraction}`}`;
  }

  function invoiceMoney(value, currency = 'KES') {
    return invoiceMoneyCents(invoiceCents(value), currency);
  }

  function invoiceDateLabel(value) {
    if (!value) return '—';
    const date = new Date(`${value.slice(0, 10)}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'Africa/Nairobi' }).format(date);
  }

  function selectInvoiceStatus(status) {
    state.invoiceStatus = status;
    document.querySelectorAll('[data-invoice-status]').forEach((tab) => {
      const active = tab.dataset.invoiceStatus === status;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
  }

  function selectQuoteStatus(status) {
    state.status = status;
    document.querySelectorAll('[data-quote-status]').forEach((tab) => {
      const active = tab.dataset.quoteStatus === status;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
  }

  async function loadInvoices() {
    const query = new URLSearchParams({ status: state.invoiceStatus, search: state.invoiceSearch, page: String(state.invoicePage) });
    const data = await api(`/invoices?${query}`);
    state.invoiceTotal = data.total;
    const maxPage = Math.max(1, Math.ceil(data.total / state.invoicePageSize));
    if (state.invoicePage > maxPage) {
      state.invoicePage = maxPage;
      return loadInvoices();
    }
    const rows = byId('invoiceRows');
    if (!rows) throw new Error('Invoice list markup is unavailable.');
    rows.replaceChildren();
    (data.items || []).forEach((invoice) => {
      const row = document.createElement('tr');
      const numberCell = document.createElement('td');
      const view = makeElement('button', 'reference-link', invoice.invoice_number);
      view.type = 'button';
      view.dataset.invoiceAction = 'view';
      view.dataset.invoiceId = invoice.id;
      numberCell.append(view);
      row.append(numberCell);
      const customer = makeElement('td', 'customer-cell');
      customer.append(makeElement('strong', '', invoice.customer_name));
      customer.append(makeElement('span', '', invoice.company_name || invoice.customer_email || ''));
      row.append(customer);
      row.append(makeElement('td', '', invoiceDateLabel(invoice.invoice_date)));
      row.append(makeElement('td', '', invoiceDateLabel(invoice.due_date)));
      row.append(makeElement('td', '', invoiceMoney(invoice.total, invoice.currency)));
      const statusCell = document.createElement('td');
      statusCell.append(makeElement('span', `invoice-status-badge ${invoice.status}`, invoice.status === 'paid' ? 'Paid' : 'Unpaid'));
      row.append(statusCell);
      const actions = makeElement('td', 'invoice-row-actions');
      const actionButton = (label, action) => {
        const button = makeElement('button', 'text-button', label);
        button.type = 'button';
        button.dataset.invoiceAction = action;
        button.dataset.invoiceId = invoice.id;
        actions.append(button);
      };
      actionButton('View', 'view');
      actionButton('Edit', 'edit');
      const download = makeElement('a', 'text-button', 'PDF');
      download.href = `/api/admin/invoices/${encodeURIComponent(invoice.id)}/pdf`;
      download.setAttribute('download', `${invoice.invoice_number}.pdf`);
      actions.append(download);
      if (invoice.status === 'new') actionButton('Mark paid', 'paid');
      row.append(actions);
      rows.append(row);
    });
    const empty = byId('invoicesEmpty');
    if (empty) empty.hidden = (data.items || []).length > 0;
    const first = data.total ? ((state.invoicePage - 1) * state.invoicePageSize) + 1 : 0;
    const last = Math.min(state.invoicePage * state.invoicePageSize, data.total);
    setText('invoicePageSummary', `Showing ${first}–${last} of ${data.total} invoices`);
    const previous = byId('invoicePreviousPage');
    const next = byId('invoiceNextPage');
    if (previous) previous.disabled = state.invoicePage <= 1;
    if (next) next.disabled = last >= data.total;
  }

  function setInvoiceProducts() {
    try {
      state.invoiceProducts = typeof window.getAllProducts === 'function' ? window.getAllProducts() : [];
    } catch (error) {
      console.error('[Alipen admin] Product catalogue could not be read for invoices.', error);
      state.invoiceProducts = [];
    }
  }

  function invoiceLineElement(item = {}) {
    const row = makeElement('div', 'invoice-line-item');
    row.dataset.productSlug = item.product_slug || '';
    const field = (label, name, value, type = 'text', attrs = {}) => {
      const wrap = makeElement('label', '', label);
      const input = document.createElement(type === 'textarea' ? 'textarea' : 'input');
      if (type !== 'textarea') input.type = type;
      input.dataset.field = name;
      if (value !== undefined && value !== null) input.value = value;
      Object.entries(attrs).forEach(([key, val]) => input.setAttribute(key, String(val)));
      wrap.append(input);
      row.append(wrap);
      return input;
    };
    field('Item name', 'name', item.name || '', 'text', { maxlength: 240, required: true });
    field('Description', 'description', item.description || '', 'textarea', { maxlength: 1000, rows: 2 });
    field('Quantity', 'quantity', item.quantity || '1', 'number', { min: '0.001', step: '0.001', required: true });
    field('Unit price', 'unit_price', item.unit_price ?? '', 'number', { min: '0', step: '0.01', required: true });
    const total = makeElement('div', 'invoice-line-total', 'KES 0.00');
    total.dataset.lineTotal = 'true';
    row.append(total);
    const remove = makeElement('button', 'invoice-remove-item', 'Remove');
    remove.type = 'button';
    remove.dataset.removeInvoiceItem = 'true';
    row.append(remove);
    if (state.invoiceEditing?.status === 'paid') {
      row.querySelectorAll('input, textarea, button').forEach((control) => { control.disabled = true; });
    }
    return row;
  }

  function calculateInvoiceTotals() {
    const itemsHost = byId('invoiceLineItems');
    const currency = byId('invoiceCurrency')?.value.toUpperCase() || 'KES';
    const cents = (value) => {
      const text = String(value || '0').trim();
      if (!/^\d{1,12}(?:\.\d{0,2})?$/.test(text)) return 0n;
      const [whole, fraction = ''] = text.split('.');
      return BigInt(whole) * 100n + BigInt((fraction + '00').slice(0, 2));
    };
    const milli = (value) => {
      const text = String(value || '0').trim();
      if (!/^\d{1,6}(?:\.\d{0,3})?$/.test(text)) return 0n;
      const [whole, fraction = ''] = text.split('.');
      return BigInt(whole) * 1000n + BigInt((fraction + '000').slice(0, 3));
    };
    const format = (amount) => invoiceMoneyCents(amount, currency);
    let subtotal = 0n;
    itemsHost?.querySelectorAll('.invoice-line-item').forEach((row) => {
      const quantity = milli(row.querySelector('[data-field="quantity"]')?.value);
      const unitPrice = cents(row.querySelector('[data-field="unit_price"]')?.value);
      const total = (quantity * unitPrice + 500n) / 1000n;
      subtotal += total;
      const totalNode = row.querySelector('[data-line-total]');
      if (totalNode) totalNode.textContent = format(total);
    });
    const discount = cents(byId('invoiceDiscount')?.value);
    const rate = cents(byId('invoiceTaxRate')?.value);
    const taxable = subtotal > discount ? subtotal - discount : 0n;
    const tax = (taxable * rate + 5000n) / 10000n;
    const total = taxable + tax;
    const summary = byId('invoiceTotals');
    if (!summary) return;
    summary.replaceChildren();
    [['Subtotal', subtotal], ['Discount', discount], [`Tax (${byId('invoiceTaxRate')?.value || '0'}%)`, tax], ['Grand total', total]].forEach(([label, amount], index) => {
      const line = makeElement('div', `invoice-total-row${index === 3 ? ' grand' : ''}`);
      line.append(makeElement('span', '', label), makeElement('strong', '', format(amount)));
      summary.append(line);
    });
  }

  function addInvoiceItem(item = {}) {
    const host = byId('invoiceLineItems');
    if (!host || host.children.length >= 100) {
      showNotice('An invoice can contain up to 100 items.', true);
      return;
    }
    host.append(invoiceLineElement(item));
    calculateInvoiceTotals();
  }

  function invoiceFormPayload() {
    return {
      quote_reference: byId('invoiceQuoteReference').value || null,
      customer_name: byId('invoiceCustomerName').value,
      customer_email: byId('invoiceCustomerEmail').value,
      company_name: byId('invoiceCompanyName').value,
      customer_address: byId('invoiceCustomerAddress').value,
      invoice_date: byId('invoiceDate').value,
      due_date: byId('invoiceDueDate').value,
      currency: byId('invoiceCurrency').value,
      discount_amount: byId('invoiceDiscount').value || '0',
      tax_rate: byId('invoiceTaxRate').value || '0',
      notes: byId('invoiceNotes').value,
      payment_instructions: byId('invoicePaymentInstructions').value,
      items: [...byId('invoiceLineItems').querySelectorAll('.invoice-line-item')].map((row) => ({
        product_slug: row.dataset.productSlug || null,
        name: row.querySelector('[data-field="name"]').value,
        description: row.querySelector('[data-field="description"]').value,
        quantity: row.querySelector('[data-field="quantity"]').value,
        unit_price: row.querySelector('[data-field="unit_price"]').value,
      })),
    };
  }

  function openInvoiceEditor(invoice = null, quote = null) {
    state.invoiceEditing = invoice;
    const form = byId('invoiceEditorForm');
    if (!form) return;
    form.reset();
    byId('invoiceLineItems').replaceChildren();
    setValue('invoiceId', invoice?.id || '');
    setValue('invoiceQuoteReference', invoice?.quote_reference || quote?.reference || '');
    setText('invoiceEditorTitle', invoice ? `Edit ${invoice.invoice_number}` : 'Create invoice');
    setText('invoiceNumberHint', invoice ? `Invoice number: ${invoice.invoice_number}${invoice.status === 'paid' ? ' · paid financial details are locked' : ''}` : 'Invoice number will be assigned when saved.');
    setValue('invoiceCustomerName', invoice?.customer_name || quote?.name || '');
    setValue('invoiceCustomerEmail', invoice?.customer_email || quote?.email || '');
    setValue('invoiceCompanyName', invoice?.company_name || quote?.facility || '');
    setValue('invoiceCustomerAddress', invoice?.customer_address || '');
    setValue('invoiceDate', invoice?.invoice_date || nairobiToday());
    setValue('invoiceDueDate', invoice?.due_date || nairobiToday());
    setValue('invoiceCurrency', invoice?.currency || 'KES');
    setValue('invoiceDiscount', invoice?.discount_amount || '0.00');
    setValue('invoiceTaxRate', invoice?.tax_rate || '0.00');
    setValue('invoiceNotes', invoice?.notes || '');
    setValue('invoicePaymentInstructions', invoice?.payment_instructions || '[Insert verified payment instructions]');
    (invoice?.items || quote?.items || []).forEach((item) => addInvoiceItem({
      product_slug: item.product_slug || item.slug || '',
      name: item.name || item.shortName || '',
      description: item.description || '',
      quantity: item.quantity || 1,
      unit_price: item.unit_price ?? item.unitPrice ?? '',
    }));
    const paid = invoice?.status === 'paid';
    ['invoiceCurrency', 'invoiceDiscount', 'invoiceTaxRate'].forEach((id) => { byId(id).disabled = paid; });
    byId('addCustomInvoiceItem').disabled = paid;
    byId('invoiceProductSearch').disabled = paid;
    byId('saveInvoice').textContent = invoice ? 'Save changes' : 'Save invoice';
    calculateInvoiceTotals();
    const dialog = byId('invoiceEditorDialog');
    if (!dialog.open) dialog.showModal();
  }

  function renderInvoiceDetails(invoice) {
    const host = byId('invoiceDetailsContent');
    if (!host) return;
    host.replaceChildren();
    const heading = makeElement('div', 'dialog-heading');
    const title = document.createElement('div');
    title.append(makeElement('span', 'page-eyebrow', invoice.status === 'paid' ? 'PAID INVOICE' : 'NEW INVOICE'));
    const detailsTitle = makeElement('h2', '', 'Invoice details');
    detailsTitle.id = 'invoiceDetailsTitle';
    title.append(detailsTitle);
    heading.append(title);
    const close = makeElement('button', 'dialog-close', '×');
    close.type = 'button'; close.setAttribute('aria-label', 'Close invoice details');
    close.addEventListener('click', () => byId('invoiceDetailsDialog').close());
    heading.append(close);
    host.append(heading);
    const banner = makeElement('div', 'invoice-detail-header');
    banner.append(makeElement('span', '', 'ALIPEN SOLUTIONS AGENCY LTD'));
    banner.append(makeElement('strong', '', invoice.invoice_number));
    banner.append(makeElement('span', '', invoice.status === 'paid' ? 'PAID' : 'PAYMENT DUE'));
    host.append(banner);
    const meta = makeElement('div', 'invoice-detail-meta');
    [['Bill to', [invoice.customer_name, invoice.company_name, invoice.customer_email, invoice.customer_address].filter(Boolean).join(' · ')], ['Invoice date', invoiceDateLabel(invoice.invoice_date)], ['Due date', invoiceDateLabel(invoice.due_date)], ['Quote reference', invoice.quote_reference || 'Standalone invoice'], ['Payment instructions', invoice.payment_instructions || '[Insert verified payment instructions]'], ['Notes', invoice.notes || '—']].forEach(([label, value]) => {
      const block = document.createElement('div'); block.append(makeElement('span', '', label), makeElement('strong', '', value)); meta.append(block);
    });
    host.append(meta);
    const content = makeElement('div', 'invoice-details-content');
    const tableWrap = makeElement('div', 'table-scroll');
    const table = makeElement('table', 'admin-table');
    const thead = document.createElement('thead'); const headerRow = document.createElement('tr');
    ['Item', 'Description', 'Qty', 'Unit price', 'Line total'].forEach((label) => headerRow.append(makeElement('th', '', label)));
    thead.append(headerRow); table.append(thead);
    const tbody = document.createElement('tbody');
    (invoice.items || []).forEach((item) => {
      const row = document.createElement('tr');
      [item.name, item.description || '—', item.quantity, invoiceMoney(item.unit_price, invoice.currency), invoiceMoney(item.line_total, invoice.currency)].forEach((value) => row.append(makeElement('td', '', value)));
      tbody.append(row);
    });
    table.append(tbody); tableWrap.append(table); content.append(tableWrap);
    const totals = makeElement('div', 'invoice-details-total');
    const balanceCents = invoiceCents(invoice.total) - invoiceCents(invoice.amount_paid);
    [
      ['Subtotal', invoiceMoney(invoice.subtotal, invoice.currency)],
      ['Discount', `− ${invoiceMoney(invoice.discount_amount, invoice.currency)}`],
      [`Tax (${invoice.tax_rate}%)`, invoiceMoney(invoice.tax_amount, invoice.currency)],
      ['Total', invoiceMoney(invoice.total, invoice.currency)],
      ['Amount paid', invoiceMoney(invoice.amount_paid, invoice.currency)],
      ['Balance due', invoiceMoneyCents(balanceCents, invoice.currency)],
    ].forEach(([label, value]) => {
      const line = document.createElement('p'); line.append(makeElement('span', '', label), makeElement('strong', '', value)); totals.append(line);
    });
    content.append(totals);
    if (invoice.status === 'paid') {
      const payment = makeElement('p', 'invoice-payment-meta', `Paid ${invoiceDateLabel(invoice.payment_date)}${invoice.payment_reference ? ` · Reference: ${invoice.payment_reference}` : ''}${invoice.payment_note ? ` · ${invoice.payment_note}` : ''}`);
      content.append(payment);
    }
    host.append(content);
    const actions = makeElement('div', 'invoice-details-actions');
    const button = (label, handler, primary = false) => { const item = makeElement('button', `admin-button${primary ? ' admin-button-primary' : ''}`, label); item.type = 'button'; item.addEventListener('click', handler); actions.append(item); };
    button('Download PDF', () => { window.location.assign(`/api/admin/invoices/${encodeURIComponent(invoice.id)}/pdf`); });
    button('Edit invoice', () => { byId('invoiceDetailsDialog').close(); openInvoiceEditor(invoice); });
    if (invoice.status === 'new') button('Mark as paid', () => { byId('invoiceDetailsDialog').close(); openInvoicePayment(invoice); }, true);
    host.append(actions);
    const dialog = byId('invoiceDetailsDialog');
    if (!dialog.open) dialog.showModal();
  }

  async function openInvoice(id, mode = 'view') {
    try {
      const data = await api(`/invoices/${encodeURIComponent(id)}`);
      if (!data.invoice) throw new Error('Invoice details were not returned.');
      if (mode === 'edit') openInvoiceEditor(data.invoice);
      else if (mode === 'paid') openInvoicePayment(data.invoice);
      else renderInvoiceDetails(data.invoice);
    } catch (error) {
      console.error('[Alipen admin] Invoice could not be opened.', error);
      showNotice(error.message, true);
    }
  }

  function openInvoicePayment(invoice) {
    state.invoiceEditing = invoice;
    setText('invoicePaymentPrompt', `${invoice.invoice_number} · ${invoiceMoney(invoice.total, invoice.currency)}. Confirm the full amount was received.`);
    setValue('invoicePaymentDate', nairobiToday());
    setValue('invoicePaymentReference', '');
    setValue('invoicePaymentNote', '');
    byId('invoicePaymentDialog').showModal();
  }

  function handleInvoiceListAction(event) {
    const button = event.target.closest('[data-invoice-action]');
    if (!button) return;
    const id = button.dataset.invoiceId;
    openInvoice(id, button.dataset.invoiceAction);
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
    if (name === 'quotes') {
      selectQuoteStatus('new');
      state.allQuotes = false;
      state.page = 1;
      const allRequests = byId('allRequestsFilter');
      if (allRequests) allRequests.checked = false;
    }
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
    else if (name === 'documents') loadInvoices().catch((error) => showNotice(error.message, true));
  }

  async function openQuote(reference) {
    clearNotice();
    state.currentReference = reference;
    const dialog = byId('quoteDetailDialog');
    const loading = byId('detailLoading');
    const content = byId('detailContent');
    if (!dialog || !loading || !content) {
      const error = new Error('Quote details cannot be opened because required dialog markup is missing.');
      console.error('[Alipen admin] Failed to open quote details', error);
      showNotice(error.message, true);
      return;
    }
    loading.hidden = false;
    content.hidden = true;
    state.quoteDialogScrollY = window.scrollY;
    try {
      prepareQuoteDialogViewport(dialog);
      dialog.showModal();
      const quote = await api(`/quotes/${encodeURIComponent(reference)}`);
      state.currentQuote = quote;
      setText('detailReference', quote.reference);
      byId('detailStatusBadge').replaceChildren(makeElement('span', `status-pill ${statusClass(quote.status)}`, displayStatus(quote.status)));
      setText('detailName', quote.name || '—');
      setText('detailFacility', quote.facility || '—');
      setText('detailFacilityType', quote.facility_type || '—');
      setText('detailCounty', quote.county || '—');
      setText('detailPhone', quote.phone || '—');
      setText('detailEmail', quote.email || '—');
      setText('detailDate', formatDate(quote.created_at));
      setText('detailRequirements', quote.requirements || 'No additional requirements provided.');
      setText('detailLostReason', [quote.lost_reason, quote.lost_explanation].filter(Boolean).join(' — ') || 'No reason recorded.');
      const invoiceHost = byId('detailInvoices');
      invoiceHost.replaceChildren();
      const linkedInvoices = quote.invoices || [];
      if (!linkedInvoices.length) invoiceHost.textContent = 'No invoices linked.';
      linkedInvoices.forEach((invoice) => {
        const line = makeElement('p', 'linked-invoice-row');
        const view = makeElement('button', 'reference-link', invoice.invoice_number);
        view.type = 'button';
        view.addEventListener('click', () => openInvoice(invoice.id));
        line.append(view, makeElement('span', '', `${invoice.status === 'paid' ? 'Paid' : 'Unpaid'}${invoice.payment_date ? ` · paid ${invoiceDateLabel(invoice.payment_date)}` : ''}`));
        invoiceHost.append(line);
      });
      byId('createInvoiceFromQuote').disabled = quote.status === 'lost';
      byId('markQuoteLost').hidden = quote.status === 'lost' || quote.status === 'completed';
      setValue('followUpDate', quote.follow_up_date || '');
      setValue('followUpNote', quote.follow_up_note || '');
      byId('followUpCompleted').checked = Boolean(quote.follow_up_completed);
      const itemList = byId('detailItems');
      itemList.replaceChildren();
      const items = Array.isArray(quote.items) ? quote.items : [];
      if (items.length) {
        items.forEach((item) => itemList.append(makeElement('li', '', `${item.name || 'Medical product'} — Qty: ${item.quantity || 1}`)));
      } else {
        itemList.append(makeElement('li', '', 'General catalogue and procurement inquiry'));
      }
      await loadPrivateNotes(quote.reference);
      loading.hidden = true;
      content.hidden = false;
    } catch (error) {
      if (dialog.open) dialog.close();
      else restoreQuoteDialogViewport(dialog);
      console.error('[Alipen admin] Failed to load quote details', error);
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
      setText('loginButton', 'Signing in…');
      const formData = new FormData(form);
      try {
        await api('/login', {
          method: 'POST',
          body: JSON.stringify({ username: formData.get('username'), password: formData.get('password') })
        });
        form.reset();
        window.location.assign('/admin');
      } catch (exception) {
        setText('loginError', exception.message);
        error.hidden = false;
      } finally {
        button.disabled = false;
        setText('loginButton', 'Sign in securely');
      }
    });
  }

  async function initDashboard() {
    try {
      const session = await api('/session');
      state.csrfToken = session.csrfToken;
      state.isPrimary = Boolean(session.isPrimary);
      state.username = session.username;
      const usersNav = byId('adminUsersNav');
      if (usersNav) usersNav.hidden = !state.isPrimary;
      setText('adminUsernameLabel', session.username);
    } catch (error) {
      if (error.message) showNotice(error.message, true);
      console.error('[Alipen admin] Dashboard session initialization failed', error);
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
    bind('sidebarToggle', 'click', () => {
      const sidebar = byId('adminSidebar');
      const open = sidebar.classList.toggle('open');
      byId('sidebarToggle').setAttribute('aria-expanded', String(open));
    });

    bind('quoteSearch', 'input', () => {
      clearTimeout(window.adminSearchTimer);
      window.adminSearchTimer = setTimeout(() => {
        state.search = byId('quoteSearch').value.trim().slice(0, 120);
        state.page = 1;
        loadQuotes().catch((error) => showNotice(error.message, true));
      }, 250);
    });
    document.querySelectorAll('[data-quote-status]').forEach((tab) => tab.addEventListener('click', () => {
      selectQuoteStatus(tab.dataset.quoteStatus);
      state.allQuotes = false;
      byId('allRequestsFilter').checked = false;
      state.page = 1;
      loadQuotes().catch((error) => showNotice(error.message, true));
    }));
    bind('allRequestsFilter', 'change', () => {
      state.allQuotes = byId('allRequestsFilter').checked;
      state.page = 1;
      loadQuotes().catch((error) => showNotice(error.message, true));
    });
    const applyDateFilters = () => {
      state.dateFrom = byId('dateFromFilter').value;
      state.dateTo = byId('dateToFilter').value;
      state.page = 1;
      loadQuotes().catch((error) => showNotice(error.message, true));
    };
    bind('dateFromFilter', 'change', applyDateFilters);
    bind('dateToFilter', 'change', applyDateFilters);
    bind('followUpFilter', 'change', () => {
      state.followUp = byId('followUpFilter').checked ? 'due' : 'all';
      state.page = 1;
      loadQuotes().catch((error) => showNotice(error.message, true));
    });
    bind('followUpDate', 'change', () => {
      byId('followUpCompleted').checked = false;
    });
    bind('clearFilters', 'click', () => {
      state.search = '';
      state.allQuotes = true;
      state.dateFrom = '';
      state.dateTo = '';
      state.followUp = 'all';
      state.page = 1;
      setValue('quoteSearch', '');
      setValue('dateFromFilter', '');
      setValue('dateToFilter', '');
      byId('followUpFilter').checked = false;
      byId('allRequestsFilter').checked = true;
      loadQuotes().catch((error) => showNotice(error.message, true));
    });
    bind('previousPage', 'click', () => {
      if (state.page > 1) { state.page -= 1; loadQuotes().catch((error) => showNotice(error.message, true)); }
    });
    bind('nextPage', 'click', () => {
      if (state.page * state.pageSize < state.total) { state.page += 1; loadQuotes().catch((error) => showNotice(error.message, true)); }
    });
    bind('closeDetail', 'click', () => byId('quoteDetailDialog')?.close());
    bind('createInvoiceFromQuote', 'click', () => {
      if (!state.currentQuote) { showNotice('Open a quote before creating an invoice from it.', true); return; }
      byId('quoteDetailDialog')?.close();
      showView('documents');
      openInvoiceEditor(null, state.currentQuote);
    });
    const quoteDialog = byId('quoteDetailDialog');
    if (quoteDialog) {
      quoteDialog.addEventListener('click', (event) => {
        if (event.target === quoteDialog) quoteDialog.close();
      });
      quoteDialog.addEventListener('close', () => {
        restoreQuoteDialogViewport(quoteDialog);
        window.requestAnimationFrame(() => window.scrollTo(0, state.quoteDialogScrollY));
      });
    } else {
      console.error('[Alipen admin] Missing #quoteDetailDialog; quote details are unavailable.');
      showNotice('Quote details are unavailable because the details dialog is missing.', true);
    }
    bind('privateNoteForm', 'submit', async (event) => {
      event.preventDefault();
      const input = byId('privateNoteInput');
      try {
        await api(`/quotes/${encodeURIComponent(state.currentReference)}/notes`, { method: 'POST', body: JSON.stringify({ content: input.value }) });
        input.value = '';
        await loadPrivateNotes(state.currentReference);
        showNotice('Private note saved.');
      } catch (error) { showNotice(error.message, true); }
    });
    bind('saveFollowUp', 'click', async () => {
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
      bind('createAdminUserForm', 'submit', async (event) => {
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
      bind('closeAdminUserDialog', 'click', () => byId('adminUserDialog')?.close());
      bind('cancelAdminUserEdit', 'click', () => byId('adminUserDialog')?.close());
      bind('editAdminUserForm', 'submit', async (event) => {
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
    bind('statusForm', 'submit', (event) => event.preventDefault());
    bind('markQuoteLost', 'click', () => { setValue('lostReason', ''); setValue('lostExplanation', ''); byId('lostQuoteDialog').showModal(); });
    bind('closeLostQuote', 'click', () => byId('lostQuoteDialog').close());
    bind('cancelLostQuote', 'click', () => byId('lostQuoteDialog').close());
    bind('lostQuoteForm', 'submit', async (event) => {
      event.preventDefault();
      const button = byId('confirmLostQuote');
      button.disabled = true;
      try {
        await api(`/quotes/${encodeURIComponent(state.currentReference)}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ status: 'lost', lost_reason: byId('lostReason').value, lost_explanation: byId('lostExplanation').value })
        });
        byId('lostQuoteDialog').close();
        byId('quoteDetailDialog').close();
        showNotice('Quote marked as Lost.');
        await Promise.all([loadOverview(), loadQuotes()]);
      } catch (error) {
        showNotice(error.message, true);
      } finally {
        button.disabled = false;
      }
    });
    bind('logoutButton', 'click', async () => {
      try { await api('/logout', { method: 'POST', body: '{}' }); }
      catch (error) {
        // Continue to login when the server session has already expired, but
        // retain a diagnostic for unexpected network/server failures.
        console.warn('[Alipen admin] Logout request did not complete; redirecting to sign in.', error);
      }
      state.csrfToken = '';
      window.location.assign('/admin/login');
    });

    setInvoiceProducts();
    document.querySelectorAll('[data-invoice-status]').forEach((button) => button.addEventListener('click', () => {
      selectInvoiceStatus(button.dataset.invoiceStatus);
      state.invoicePage = 1;
      loadInvoices().catch((error) => showNotice(error.message, true));
    }));
    bind('invoiceSearch', 'input', () => {
      clearTimeout(state.invoiceSearchTimer);
      state.invoiceSearchTimer = setTimeout(() => {
        state.invoiceSearch = byId('invoiceSearch').value.trim().slice(0, 120);
        state.invoicePage = 1;
        loadInvoices().catch((error) => showNotice(error.message, true));
      }, 250);
    });
    bind('invoiceRows', 'click', handleInvoiceListAction);
    bind('invoicePreviousPage', 'click', () => {
      if (state.invoicePage > 1) { state.invoicePage -= 1; loadInvoices().catch((error) => showNotice(error.message, true)); }
    });
    bind('invoiceNextPage', 'click', () => {
      if (state.invoicePage * state.invoicePageSize < state.invoiceTotal) { state.invoicePage += 1; loadInvoices().catch((error) => showNotice(error.message, true)); }
    });
    bind('createNewInvoice', 'click', () => openInvoiceEditor());
    bind('closeInvoiceEditor', 'click', () => byId('invoiceEditorDialog')?.close());
    bind('cancelInvoiceEditor', 'click', () => byId('invoiceEditorDialog')?.close());
    bind('invoiceLineItems', 'input', calculateInvoiceTotals);
    bind('invoiceLineItems', 'click', (event) => {
      if (event.target.closest('[data-remove-invoice-item]')) {
        event.target.closest('.invoice-line-item')?.remove();
        calculateInvoiceTotals();
      }
    });
    ['invoiceDiscount', 'invoiceTaxRate', 'invoiceCurrency'].forEach((id) => bind(id, 'input', calculateInvoiceTotals));
    bind('addCustomInvoiceItem', 'click', () => {
      addInvoiceItem({});
      byId('invoiceLineItems')?.lastElementChild?.querySelector('[data-field="name"]')?.focus();
    });
    bind('invoiceProductSearch', 'input', () => {
      const results = byId('invoiceProductResults');
      if (!results) return;
      const term = byId('invoiceProductSearch').value.trim().toLocaleLowerCase();
      results.replaceChildren();
      if (!term) { results.hidden = true; return; }
      const matches = state.invoiceProducts.filter((product) => `${product.name} ${product.shortName || ''} ${product.description || ''}`.toLocaleLowerCase().includes(term)).slice(0, 12);
      matches.forEach((product) => {
        const option = makeElement('button', 'invoice-product-option');
        option.type = 'button';
        option.append(makeElement('strong', '', product.name));
        option.append(makeElement('span', '', product.description || 'Catalogue product'));
        option.addEventListener('click', () => {
          addInvoiceItem({ product_slug: product.slug, name: product.name, description: product.description || '', quantity: 1, unit_price: '' });
          results.hidden = true;
          setValue('invoiceProductSearch', '');
        });
        results.append(option);
      });
      if (!matches.length) results.append(makeElement('p', 'empty-state', 'No matching catalogue products.'));
      results.hidden = false;
    });
    bind('invoiceEditorForm', 'submit', async (event) => {
      event.preventDefault();
      const button = byId('saveInvoice');
      const payload = invoiceFormPayload();
      button.disabled = true;
      try {
        const existingId = byId('invoiceId').value;
        const result = await api(existingId ? `/invoices/${encodeURIComponent(existingId)}` : '/invoices', {
          method: existingId ? 'PATCH' : 'POST', body: JSON.stringify(payload)
        });
        if (!result.invoice) throw new Error('The server did not return the saved invoice.');
        byId('invoiceEditorDialog').close();
        selectInvoiceStatus(result.invoice.status || 'new');
        state.invoicePage = 1;
        showView('documents');
        showNotice(`Invoice ${result.invoice.invoice_number} saved.`);
        renderInvoiceDetails(result.invoice);
      } catch (error) {
        console.error('[Alipen admin] Invoice could not be saved.', error);
        showNotice(error.message, true);
      } finally { button.disabled = false; }
    });
    bind('closeInvoicePayment', 'click', () => byId('invoicePaymentDialog')?.close());
    bind('cancelInvoicePayment', 'click', () => byId('invoicePaymentDialog')?.close());
    bind('invoicePaymentForm', 'submit', async (event) => {
      event.preventDefault();
      const invoice = state.invoiceEditing;
      if (!invoice) return;
      const form = event.currentTarget;
      const button = form.querySelector('[type="submit"]');
      button.disabled = true;
      try {
        const result = await api(`/invoices/${encodeURIComponent(invoice.id)}/paid`, {
          method: 'POST', body: JSON.stringify({
            payment_date: byId('invoicePaymentDate').value,
            payment_reference: byId('invoicePaymentReference').value,
            payment_note: byId('invoicePaymentNote').value,
          })
        });
        byId('invoicePaymentDialog').close();
        selectInvoiceStatus('paid');
        state.invoicePage = 1;
        await loadInvoices();
        showNotice(`Invoice ${result.invoice.invoice_number} marked as paid.`);
        renderInvoiceDetails(result.invoice);
      } catch (error) {
        console.error('[Alipen admin] Invoice payment could not be recorded.', error);
        showNotice(error.message, true);
      } finally { button.disabled = false; }
    });

    // Attach interactions before loading dashboard data. Rendering/API errors
    // must never leave navigation, filtering, or logout inert.
    loadOverview().catch((error) => {
      console.error('[Alipen admin] Dashboard overview request failed', error);
      showNotice(error.message || 'Could not load the dashboard overview.', true);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.adminPage === 'login') initLogin();
    if (document.body.dataset.adminPage === 'dashboard') initDashboard();
  });
})();
