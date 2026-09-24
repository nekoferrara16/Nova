'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const currency = (cents, compact = false) => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits:compact ? 0 : 2}).format(cents / 100);
const today = () => { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`; };
const monthLabel = month => new Date(`${month}-15T12:00:00`).toLocaleDateString('en-US', {month:'long', year:'numeric'});
const dateLabel = value => new Date(`${value}T12:00:00`).toLocaleDateString('en-US', {month:'short', day:'numeric'});
const paths = {
  overview:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  transactions:'<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
  budget:'<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 7h8M8 12h2m4 0h2M8 16h2m4 0h2"/>',
  wallet:'<path d="M20 7H5a2 2 0 0 1 0-4h13v4M5 7H3v12a2 2 0 0 0 2 2h15V7Z"/><path d="M20 11h-5v6h5m-2-3h.1"/>',
  insight:'<path d="M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 2H9s0-1-1-2ZM12 1V0M3 4 2 3m19 1 1-1"/>',
  shield:'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
  settings:'<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 3 2 2-1 3 2 3 3-1 3 4 3-2 1-3 3-1 2-3-2-3-3-1-1-3-3-1-3 2Z"/>',
  logout:'<path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18m-13 5h2m4 0h2"/>',
  upload:'<path d="M4 15v5h16v-5M12 16V3m-5 5 5-5 5 5"/>',
  download:'<path d="M4 15v5h16v-5M12 3v13m-5-5 5 5 5-5"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5m0 3h.01"/>',
  menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
  growth:'<path d="m3 17 6-6 4 4 8-10m-6 0h6v6"/>',
  down:'<path d="M12 3v18m-6-6 6 6 6-6"/>',
  up:'<path d="M12 21V3m-6 6 6-6 6 6"/>',
  card:'<rect x="2" y="4" width="20" height="16" rx="3"/><path d="M2 9h20M6 15h4"/>',
  bank:'<path d="m3 8 9-5 9 5H3Zm0 13h18M5 10v8m7-8v8m7-8v8M3 18h18"/>',
  bag:'<path d="M5 7h14l2 14H3L5 7Zm3 0V5a4 4 0 0 1 8 0v2"/>',
  edit:'<path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.wallet}</svg>`;
function hydrateIcons(root = document) { $$('[data-icon]', root).forEach(el => { el.outerHTML = icon(el.dataset.icon); }); }
hydrateIcons();

const state = {user:null, data:null, view:'overview', month:today().slice(0,7), register:false, page:0, search:'', category:'', account:'', request:0};
const colors = ['#538363','#94a985','#c2cead','#d8ba83','#98adac','#b4b5a4'];
let toastTimer;
function toast(message, error = false) { const el = $('#toast'); el.textContent = message; el.classList.toggle('error', error); el.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, error ? 7000 : 4500); }
function showAuth() { $('#app').hidden = true; $('#auth').hidden = false; $('#boot').hidden = true; state.user = null; state.data = null; $$('dialog[open]').forEach(el => el.close()); }
async function api(path, options = {}) {
  const headers = {'Content-Type':'application/json'};
  if (state.user) headers['X-CSRF-Token'] = state.user.csrf;
  const response = await fetch(path, {...options, headers, credentials:'same-origin'});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !['/api/login','/api/register','/api/me'].includes(path)) showAuth();
    const detail = Array.isArray(body.detail) ? body.detail.map(e => `${e.loc.at(-1)}: ${e.msg}`).join('; ') : body.detail;
    throw new Error(detail || 'Something went wrong. Please try again.');
  }
  return body;
}
const send = (path, data = {}, method = 'POST') => api(path, {method, body:JSON.stringify(data)});
async function refresh() {
  const request = ++state.request;
  $('#save-status').textContent = 'Updating…';
  try {
    const data = await api(`/api/dashboard?month=${encodeURIComponent(state.month)}`);
    if (request !== state.request || !state.user) return;
    state.data = data;
    $('#as-of').textContent = `As of ${dateLabel(data.as_of)}, ${data.as_of.slice(0,4)}`;
    render();
    $('#save-status').textContent = 'All changes saved';
  } catch (error) { $('#save-status').textContent = 'Could not refresh'; throw error; }
}
async function enterWorkspace() {
  state.user = await api('/api/me');
  $('#auth').hidden = true; $('#boot').hidden = true; $('#app').hidden = false;
  $('#username').textContent = state.user.username;
  $('#avatar').textContent = state.user.username.slice(0,2).toUpperCase();
  $('#month').value = state.month;
  state.view = ['overview','transactions','budgets','accounts','insights','settings'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  $('#page-content').innerHTML = '<div class="loading-state">Gathering your financial picture…</div>';
  await refresh();
}
$('#auth-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = $('#auth-submit'); button.disabled = true; $('#auth-error').textContent = '';
  try { await send(state.register ? '/api/register' : '/api/login', Object.fromEntries(new FormData(event.target))); event.target.reset(); await enterWorkspace(); }
  catch (error) { $('#auth-error').textContent = error.message; }
  finally { button.disabled = false; }
});
$('#auth-toggle').addEventListener('click', () => {
  state.register = !state.register;
  $('#auth-title').textContent = state.register ? 'A fresh perspective.' : 'Welcome back.';
  $('#auth-description').textContent = state.register ? 'Create your own private financial workspace.' : 'Sign in to see the bigger picture.';
  $('#auth-submit').innerHTML = `${state.register ? 'Create workspace' : 'Sign in'} ${icon('arrow')}`;
  $('#auth-toggle-label').textContent = state.register ? 'Already have a workspace?' : 'New here?';
  $('#auth-toggle').textContent = state.register ? 'Sign in' : 'Create a workspace';
  $('#auth-form [name=password]').autocomplete = state.register ? 'new-password' : 'current-password';
  $('#auth-error').textContent = '';
});
$('#logout').addEventListener('click', () => run(async () => { await send('/api/logout'); state.request++; showAuth(); }));
$('#month').addEventListener('change', event => { if (event.target.value) { state.month = event.target.value; state.page = 0; run(refresh); } });
$('#mobile-menu').addEventListener('click', () => { const open = $('#sidebar').classList.toggle('open'); $('#mobile-menu').setAttribute('aria-expanded', open); });
$('#help').addEventListener('click', () => $('#help-dialog').showModal());
async function run(task) { try { await task(); } catch (error) { toast(error.message || 'Unable to complete this action.', true); } }
function changeView(view) {
  state.view = view; state.page = 0; location.hash = view;
  $('#sidebar').classList.remove('open'); $('#mobile-menu').setAttribute('aria-expanded','false');
  render();
}
window.addEventListener('hashchange', () => { const view = location.hash.slice(1); if (['overview','transactions','budgets','accounts','insights','settings'].includes(view) && state.data && state.view !== view) changeView(view); });
document.addEventListener('click', event => {
  const close = event.target.closest('[data-close]'); if (close) $(`#${close.dataset.close}`).close();
  const nav = event.target.closest('[data-view]'); if (nav && state.data) changeView(nav.dataset.view);
  const action = event.target.closest('[data-action]');
  if (action && !action.disabled && state.data) run(() => handleAction(action.dataset.action, action.dataset.id));
});

function empty(title, detail, action = '', label = '') { return `<div class="empty">${icon('insight')}<strong>${escapeHTML(title)}</strong><p>${escapeHTML(detail)}</p>${action ? `<button class="button" data-action="${action}">${icon('plus')}${escapeHTML(label)}</button>` : ''}</div>`; }
function panelHead(title, sub, button = '') { return `<div class="panel-head"><div><h2>${title}</h2>${sub ? `<p>${sub}</p>` : ''}</div>${button}</div>`; }
function viewLink(view, label) { return `<button class="text-link" data-view="${view}">${label}${icon('arrow')}</button>`; }
function accountIcon(kind) { return ['credit','loan'].includes(kind) ? 'card' : kind === 'investment' ? 'growth' : 'bank'; }
function render() {
  if (!state.data) return;
  const views = {
    overview:['Your financial overview', "A little perspective on where you are, and where you're going.", overviewPage],
    transactions:['Every little detail', 'Your transactions, together in one place.', transactionsPage],
    budgets:['Make room for what matters', 'A thoughtful plan for the month ahead.', budgetsPage],
    accounts:['The whole picture', 'Your assets and liabilities, brought together.', accountsPage],
    insights:['A little more perspective', 'Useful observations, grounded in your recorded data.', insightsPage],
    settings:['Your workspace, your way', 'Keep your data accessible and in your control.', settingsPage],
  };
  const [title, subtitle, renderPage] = views[state.view];
  $('#page-title').textContent = title; $('#page-subtitle').textContent = subtitle;
  $('#breadcrumb').textContent = state.view === 'settings' ? 'Settings & exports' : state.view[0].toUpperCase() + state.view.slice(1);
  $$('.nav [data-view]').forEach(el => { el.classList.toggle('active', el.dataset.view === state.view); el.setAttribute('aria-current', el.dataset.view === state.view ? 'page' : 'false'); });
  $('#page-content').innerHTML = renderPage();
  if (state.view === 'transactions') wireFilters();
}
function overviewPage() {
  const d = state.data, s = d.summary;
  const first = !d.accounts.length ? `<div class="onboarding">${icon('insight')}<div><strong>Your next chapter starts here.</strong><p>Add an account, import a statement, and let the picture come together.</p></div><button class="button primary" data-action="account">${icon('plus')}Add your first account</button></div>` : '';
  const metrics = [
    ['Net worth',s.net_worth_cents,'wallet',`${currency(s.assets_cents, true)} assets · ${currency(s.liabilities_cents, true)} liabilities`,'featured'],
    ['Monthly income',s.income_cents,'down','Recorded income this month',''],
    ['Monthly spending',s.expense_cents,'up','After refunds · excludes transfers',''],
    ['Cash flow',s.cash_flow_cents,'growth',s.savings_rate === null ? 'Add income to see your margin' : `${s.savings_rate}% of income retained`,''],
  ];
  return `${first}<div class="cards">${metrics.map(([label,value,glyph,note,cls]) => `<article class="card ${cls}"><div class="card-label">${label}${icon(glyph)}</div><div class="card-value ${value < 0 ? 'negative' : ''}">${currency(value)}</div><div class="card-foot">${escapeHTML(note)}</div></article>`).join('')}</div>
  <div class="dashboard-grid">
    <section class="panel">${panelHead('Money in, money out','Your cash flow over the last six months', '<div class="legend"><span><i class="dot"></i>Income</span><span><i class="dot expense"></i>Spending</span></div>')}<div class="chart-summary"><div><small>Income this month</small><strong>${currency(s.income_cents)}</strong></div><div><small>Spending this month</small><strong>${currency(s.expense_cents)}</strong></div></div>${cashFlowChart()}<div class="chart-caption">${icon('calendar').replace('class="icon"','class="icon" style="height:11px;width:11px;vertical-align:middle"')} ${monthLabel(d.trend[0].month)} – ${monthLabel(d.month)} · Transfers excluded</div></section>
    <section class="panel">${panelHead('Where it goes','A closer look at your monthly spending')}${spendingChart()}</section>
    <section class="panel">${panelHead('A plan for your spending',monthLabel(d.month),viewLink('budgets','View budgets'))}${budgetList(d.budgets.slice(0,4))}</section>
    <section class="panel">${panelHead('Your accounts','Balances from your recorded activity',viewLink('accounts','View all'))}${accountList(d.accounts.slice(0,4))}</section>
    <section class="panel recent-panel">${panelHead('Recent transactions','The small details behind the bigger picture',viewLink('transactions','View all transactions'))}${transactionTable(d.transactions.filter(r => r.date.startsWith(state.month)).slice(0,5),false)}</section>
  </div>${insightStrip()} `;
}
function cashFlowChart() {
  const trend = state.data.trend;
  const values = trend.flatMap(t => [t.income_cents,t.expense_cents]);
  const maximum = Math.max(100,...values), minimum = Math.min(0,...values);
  const width = 570, height = 205, span = 150;
  const y = value => 172 - (value-minimum)/(maximum-minimum)*span;
  const bottom = y(0);
  const gridValues = minimum < 0 ? [minimum,0,maximum] : [0,maximum/2,maximum];
  const grid = gridValues.map(value => `<line class="grid" x1="49" x2="562" y1="${y(value)}" y2="${y(value)}"/><text x="0" y="${y(value)+3}">${currency(value,true)}</text>`).join('');
  const bars = trend.map((t,i) => {
    const x = 69 + i * 82;
    const bar = (value,offset,color,label) => `<rect x="${x+offset}" y="${value >= 0 ? y(value) : bottom}" width="18" height="${Math.abs(y(value)-bottom)}" rx="3" fill="${color}"><title>${monthLabel(t.month)} · ${label}: ${currency(value)}</title></rect>`;
    return `${bar(t.income_cents,0,'#578466','Income')}${bar(t.expense_cents,23,'#d1ddc9','Spending')}<text x="${x+20}" y="198" text-anchor="middle">${new Date(t.month+'-15T12:00:00').toLocaleDateString('en-US',{month:'short'})}</text>`;
  }).join('');
  return `<div class="chart-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Six-month income and spending chart"><title>Recorded income and spending, ${monthLabel(trend[0].month)} to ${monthLabel(state.month)}</title>${grid}${bars}</svg></div>`;
}
function spendingChart() {
  const items = state.data.categories.filter(c => c.amount_cents > 0);
  if (!items.length) return empty('Every dollar tells a story', 'Add expenses to see how your spending comes together.','transaction','Add a transaction');
  const total = items.reduce((sum,c) => sum+c.amount_cents,0);
  const categories = items.length > 5 ? [...items.slice(0,4),{category:'Other categories',amount_cents:items.slice(4).reduce((s,c)=>s+c.amount_cents,0)}] : items;
  let offset = 0;
  const circles = categories.map((c,i) => { const length = c.amount_cents/total*100; const markup = `<circle cx="80" cy="80" r="64" fill="none" stroke="${colors[i]}" stroke-width="15" pathLength="100" stroke-dasharray="${Math.max(0,length-.8)} ${100-Math.max(0,length-.8)}" stroke-dashoffset="${-offset}"><title>${escapeHTML(c.category)}: ${currency(c.amount_cents)}</title></circle>`; offset += length; return markup; }).join('');
  return `<div class="spending-content"><div class="donut"><svg viewBox="0 0 160 160" role="img" aria-label="Spending by category">${circles}</svg><div class="donut-center"><small>Spending</small><strong>${currency(total,true)}</strong></div></div><div class="category-list">${categories.map((c,i) => `<div class="category-line"><i class="dot" style="background:${colors[i]}"></i><span class="category-name" title="${escapeHTML(c.category)}">${escapeHTML(c.category)}</span><strong>${currency(c.amount_cents,true)}</strong><small>${Math.round(c.amount_cents/total*100)}%</small></div>`).join('')}</div></div><div class="chart-caption">Positive category totals. Refund-only categories are excluded.</div>`;
}
function budgetList(budgets, full = false) {
  if (!budgets.length) return empty('Give your month a little direction','Set a spending limit for a category you want to keep an eye on.','budget','Create a budget');
  return `<div class="budget-list">${budgets.map(b => { const ratio = b.limit_cents > 0 ? b.spent_cents/b.limit_cents*100 : (b.spent_cents > 0 ? 100 : 0); return `<div><div class="budget-row-head"><span><i class="dot" style="background:${b.remaining_cents < 0 ? '#c79055' : '#8aa381'}"></i>${escapeHTML(b.category)}</span><span><strong>${currency(b.spent_cents,true)} <small>/ ${currency(b.limit_cents,true)}</small></strong>${full ? `<button class="icon-button" data-action="edit-budget" data-id="${escapeHTML(b.category)}" aria-label="Edit ${escapeHTML(b.category)} budget">${icon('edit')}</button><button class="icon-button" data-action="delete-budget" data-id="${escapeHTML(b.category)}" aria-label="Delete ${escapeHTML(b.category)} budget">${icon('trash')}</button>` : ''}</span></div><div class="progress" role="meter" aria-label="${escapeHTML(b.category)} budget used" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.max(0,Math.min(100,ratio))}"><div class="${b.remaining_cents < 0 ? 'over' : ''}" style="width:${Math.max(0,Math.min(100,ratio))}%"></div></div>${full ? `<p class="section-note">${currency(Math.abs(b.remaining_cents))} ${b.remaining_cents < 0 ? 'over budget' : 'remaining'}</p>` : ''}</div>`; }).join('')}</div><div class="budget-note">${currency(state.data.summary.budget_remaining_cents,true)} remaining across all budgeted categories.</div>`;
}
function accountList(accounts) {
  if (!accounts.length) return empty('Everything in one place','Bring your checking, savings, credit cards, and investments together.','account','Add an account');
  return `<div class="account-list">${accounts.map(a => `<div class="account-row"><div class="account-glyph">${icon(accountIcon(a.kind))}</div><div class="account-label"><strong>${escapeHTML(a.name)}</strong><small>${escapeHTML(a.institution || a.kind)}</small></div><span class="account-value ${a.balance_cents < 0 ? 'negative' : ''}">${currency(a.balance_cents)}</span></div>`).join('')}</div><div class="account-footer"><span>Total liquid balance</span><strong>${currency(state.data.summary.liquid_cents)}</strong></div>`;
}
function transactionTable(rows, editable = true) {
  if (!rows.length) return empty('A fresh page','No transactions match this view. Add an entry or import a bank statement.','transaction','Add a transaction');
  return `<div class="table-wrap"><table><thead><tr><th>Description</th><th>Date</th><th>Category</th><th>Account</th><th class="amount">Amount</th>${editable ? '<th>Actions</th>' : ''}</tr></thead><tbody>${rows.map(r => `<tr><td class="description"><div class="merchant"><span class="merchant-icon">${icon(r.kind === 'transfer' ? 'transactions' : r.kind === 'income' ? 'down' : 'bag')}</span><span>${escapeHTML(r.description)}${r.date > today() ? '<br><small>Future · not yet in totals</small>' : ''}</span></div></td><td title="${r.date}">${dateLabel(r.date)}</td><td><span class="badge">${escapeHTML(r.category)}</span></td><td>${escapeHTML(r.account_name)}</td><td class="amount ${r.amount_cents > 0 ? 'inflow' : ''}">${r.amount_cents > 0 ? '+' : '−'}${currency(Math.abs(r.amount_cents))}</td>${editable ? `<td class="row-actions">${!r.transfer_group ? `<button class="icon-button" data-action="edit-transaction" data-id="${r.id}" aria-label="Edit ${escapeHTML(r.description)}">${icon('edit')}</button>` : ''}<button class="icon-button" data-action="delete-transaction" data-id="${r.id}" aria-label="Delete ${escapeHTML(r.description)}">${icon('trash')}</button></td>` : ''}</tr>`).join('')}</tbody></table></div>`;
}
function insightStrip() {
  const insight = state.data.insights[0] || {title:'A small habit. A clearer future.',detail:'A weekly check-in keeps your financial picture up to date. You’re in control.'};
  return `<aside class="insight-strip">${icon('insight')}<div><strong>${escapeHTML(insight.title)}</strong><p>${escapeHTML(insight.detail)}</p></div><span class="tag">A LITTLE PERSPECTIVE</span></aside>`;
}
function filteredTransactions() {
  return state.data.transactions.filter(r => r.date.startsWith(state.month) && (!state.search || `${r.description} ${r.category} ${r.account_name}`.toLowerCase().includes(state.search.toLowerCase())) && (!state.category || r.category === state.category) && (!state.account || String(r.account_id) === state.account));
}
function transactionsPage() {
  const rows = filteredTransactions();
  state.page = Math.min(state.page, Math.max(0,Math.ceil(rows.length/25)-1));
  return `<div class="filterbar"><input id="search" class="search" type="search" placeholder="Search your transactions…" aria-label="Search transactions" value="${escapeHTML(state.search)}"><select id="filter-category" aria-label="Filter category"><option value="">All categories</option>${options(state.user.categories,state.category)}</select><select id="filter-account" aria-label="Filter account"><option value="">All accounts</option>${state.data.accounts.map(a => `<option value="${a.id}" ${String(a.id) === state.account ? 'selected' : ''}>${escapeHTML(a.name)}</option>`).join('')}</select><button class="button" data-action="transfer">${icon('transactions')}Transfer</button><a class="button" href="/api/export/transactions" download>${icon('download')}Export all</a></div><section class="panel"><div id="ledger-rows">${ledgerRows(rows)}</div></section><p class="section-note">Transfers are excluded from income and spending. Refunds recorded as expense kind reduce spending. Future-dated entries are shown here but excluded from current totals.</p>`;
}
function ledgerRows(rows) { return `${transactionTable(rows.slice(state.page*25,(state.page+1)*25))}<div class="pagination"><span>${rows.length} transactions · ${monthLabel(state.month)}</span><div class="actions"><button class="button" data-action="previous" ${state.page===0?'disabled':''}>Previous</button><span>${state.page+1} / ${Math.max(1,Math.ceil(rows.length/25))}</span><button class="button" data-action="next" ${(state.page+1)*25>=rows.length?'disabled':''}>Next</button></div></div>`; }
function wireFilters() {
  const update = () => { state.page = 0; $('#ledger-rows').innerHTML = ledgerRows(filteredTransactions()); };
  $('#search').addEventListener('input', event => { state.search = event.target.value; update(); });
  $('#filter-category').addEventListener('change', event => { state.category = event.target.value; update(); });
  $('#filter-account').addEventListener('change', event => { state.account = event.target.value; update(); });
}
function budgetsPage() {
  const s = state.data.summary;
  return `<section class="panel">${panelHead('Your monthly plan',`${monthLabel(state.month)} · ${state.data.budgets.length} category budgets`,`<button class="button primary" data-action="budget">${icon('plus')}Set a budget</button>`)}${budgetList(state.data.budgets,true)}</section><div class="insight-strip">${icon('budget')}<div><strong>Budget the categories that matter to you.</strong><p>Total recorded spending is ${currency(s.expense_cents)}. Budget remaining covers only categories with a limit; it is not your available bank balance. Budgets are specific to each month.</p></div></div>`;
}
function accountsPage() {
  return `<div class="filterbar"><button class="button primary" data-action="account">${icon('plus')}Add an account</button><button class="button" data-action="transfer">${icon('transactions')}Move money</button></div>${!state.data.accounts.length ? `<section class="panel">${accountList([])}</section>` : `<div class="section-grid">${state.data.accounts.map(a => `<article class="panel account-detail"><div class="account-row"><span class="account-glyph">${icon(accountIcon(a.kind))}</span><div class="account-label"><strong>${escapeHTML(a.name)}</strong><small>${escapeHTML(a.institution || a.kind)}</small></div></div><div class="balance ${a.balance_cents < 0 ? 'negative' : ''}">${currency(a.balance_cents)}</div><p>${a.active ? 'Recorded balance' : 'Account starts after this reporting date'} · ${escapeHTML(a.kind)}</p><div class="account-footer"><span>Opening ${dateLabel(a.opening_date)}, ${a.opening_date.slice(0,4)}</span><strong>${currency(a.opening_cents)}</strong></div><div class="actions" style="margin-top:16px"><button class="button" data-action="edit-account" data-id="${a.id}">${icon('edit')}Edit account</button><button class="icon-button" data-action="delete-account" data-id="${a.id}" aria-label="Remove ${escapeHTML(a.name)}">${icon('trash')}</button></div></article>`).join('')}</div>`}<p class="section-note">Opening balances are the balances at the start of the opening date. Credit card and loan debts count as negative balances. Investment balances reflect entered values and activity, without market price updates. Only USD is supported.</p>`;
}
function insightsPage() {
  const insights = state.data.insights.length ? state.data.insights : [{title:'Keep the picture current',detail:'Import a statement or review this month’s transactions to keep your numbers useful.',tone:'green'}];
  return `<div class="section-grid">${insights.map(i => `<article class="panel insight-card ${i.tone}">${icon('insight')}<h2>${escapeHTML(i.title)}</h2><p>${escapeHTML(i.detail)}</p></article>`).join('')}</div><section class="panel" style="margin-top:22px">${panelHead('A familiar rhythm','Potential recurring expenses · matching descriptions across three recent months')}${state.data.recurring.length ? `<div class="account-list">${state.data.recurring.map(r => `<div class="account-row"><span class="account-glyph">${icon('calendar')}</span><div class="account-label"><strong>${escapeHTML(r.description)}</strong><small>Seen in ${r.months} months</small></div><span class="account-value">${currency(r.amount_cents)}<br><small>average charge</small></span></div>`).join('')}</div>` : empty('Patterns take a little time','Import three months of history to identify possible recurring expenses.')}<p class="section-note">These are pattern-based candidates, not confirmed subscriptions or predictions. Exact descriptions must recur across three recent months with amounts within 20%.</p></section>`;
}
function settingsPage() {
  return `<section class="panel"><div class="settings-list"><div class="settings-item"><div><h2>Export your workspace</h2><p>Download accounts, transactions, and budgets as JSON. This is a portable data export, not an automatic restore file.</p></div><a class="button" href="/api/export" download>${icon('download')}Export JSON</a></div><div class="settings-item"><div><h2>A spreadsheet of your activity</h2><p>Download all transactions, across every account and month.</p></div><a class="button" href="/api/export/transactions" download>${icon('download')}Export CSV</a></div><div class="settings-item"><div><h2>A starting point for imports</h2><p>A sample CSV with signed amounts, categories, and a transfer. Use only with a test account.</p></div><a class="button" href="/static/example-transactions.csv" download>${icon('download')}Sample CSV</a></div><div class="settings-item"><div><h2>Your private workspace</h2><p>Signed in as ${escapeHTML(state.user.username)}. Your records are scoped to your account. Data is stored on the computer running novaFinance.</p></div><span class="badge">USD</span></div></div></section><p class="section-note">There is no bank connection or background synchronization. Changes are saved on the server as you make them. For complete recovery, back up the database file while the server is stopped; see the project README. Public hosting requires HTTPS and deployment configuration.</p>`;
}

function options(values, selected = '') { return values.map(v => `<option value="${escapeHTML(v)}" ${v === selected ? 'selected' : ''}>${escapeHTML(v[0].toUpperCase()+v.slice(1))}</option>`).join(''); }
function accountOptions(selected) { return state.data.accounts.map(a => `<option value="${a.id}" ${a.id === selected ? 'selected' : ''}>${escapeHTML(a.name)}</option>`).join(''); }
function field(label, name, value = '', type = 'text', extra = '', full = false) { return `<label class="field ${full ? 'full' : ''}">${label}<input name="${name}" type="${type}" value="${escapeHTML(value)}" ${extra} required></label>`; }
function select(label, name, values, full = false, extra = '') { return `<label class="field ${full ? 'full' : ''}">${label}<select name="${name}" ${extra}>${values}</select></label>`; }
let editorSave;
function openEditor(title, description, content, save, label = 'Save') {
  $('#editor-title').textContent = title; $('#editor-description').textContent = description;
  $('#editor-form').innerHTML = `${content}<p class="form-error" role="alert" id="editor-error"></p><div class="form-actions"><button type="button" class="button" data-close="editor">Cancel</button><button type="submit" class="button primary">${label}</button></div>`;
  editorSave = save; $('#editor').showModal();
}
$('#editor-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = $('[type=submit]', event.target); button.disabled = true; $('#editor-error').textContent = '';
  try { await editorSave(Object.fromEntries(new FormData(event.target))); $('#editor').close(); await refresh(); toast('Saved to your workspace.'); }
  catch (error) { if ($('#editor').open) $('#editor-error').textContent = error.message; else toast(error.message,true); }
  finally { button.disabled = false; }
});
function requireAccounts(count = 1) { if (state.data.accounts.length >= count) return true; toast(count === 1 ? 'Add an account first.' : 'Add at least two accounts to move money.'); openAccount(); return false; }
function openAccount(id) {
  const account = id ? state.data.accounts.find(a => a.id === Number(id)) : null;
  const opening = account ? account.opening_cents * (['credit','loan'].includes(account.kind) ? -1 : 1) : 0;
  openEditor(account ? 'Adjust your account' : 'A place for your money',account ? 'Opening balance corrections affect all reported balances.' : 'Add an account to your financial picture.',
    field('Account name','name',account?.name || '','text','maxlength="80" placeholder="Everyday checking"',true) + field('Institution (or Personal)','institution',account?.institution || 'Personal','text','maxlength="80"') + select('Account type','kind',options(state.user.account_kinds,account?.kind || 'checking')) + field('Opening balance ($)','balance',(opening/100).toFixed(2),'number','step="0.01"') + field('Opening date','opening_date',account?.opening_date || `${state.month}-01`,'date') + '<p class="form-note">Enter the balance at the start of this date, before the transactions you plan to add. For credit cards and loans, enter the positive amount owed. Imports before this date will be rejected. Changing an account invalidates pending import previews.</p>', data => send(account ? `/api/accounts/${account.id}` : '/api/accounts',data,account ? 'PUT' : 'POST'), account ? 'Save changes' : 'Add account');
}
function openTransaction(id) {
  if (!requireAccounts()) return;
  const row = id ? state.data.transactions.find(r => r.id === Number(id)) : null;
  const fixed = row?.source === 'csv';
  openEditor(row ? 'A little adjustment' : 'Record a transaction', fixed ? 'Update the category or kind of this imported entry.' : 'Keep the small details in view.',
    select('Account','account_id',accountOptions(row?.account_id),true,fixed?'disabled':'') + field('Description','description',row?.description || '','text',`maxlength="240" placeholder="Weekly groceries" ${fixed?'disabled':''}`,true) + field('Date','date',row?.date || (state.month === today().slice(0,7) ? today() : `${state.month}-01`),'date',fixed?'disabled':'') + field('Signed amount ($)','amount',row ? (row.amount_cents/100).toFixed(2) : '','number',`step="0.01" placeholder="-42.50" ${fixed?'disabled':''}`) + select('Kind','kind',options(['expense','income','transfer'],row?.kind || 'expense')) + select('Category','category',options(state.user.categories,row?.category || 'Uncategorized')) + '<p class="form-note">Negative amounts reduce the account balance; positive amounts add to it. A positive expense is a refund. Mark credit card payments as transfers so they do not count as spending twice.</p>',
    data => { if (fixed) Object.assign(data,{account_id:row.account_id,date:row.date,description:row.description,amount:(row.amount_cents/100).toFixed(2)}); data.account_id = Number(data.account_id); return send(row ? `/api/transactions/${row.id}` : '/api/transactions',data,row?'PUT':'POST'); });
  const kind = $('#editor-form [name=kind]'), category = $('#editor-form [name=category]');
  kind.addEventListener('change', () => { if (kind.value === 'transfer') category.value = 'Transfer'; else if (category.value === 'Transfer') category.value = kind.value === 'income' ? 'Other income' : 'Uncategorized'; });
}
function openTransfer() {
  if (!requireAccounts(2)) return;
  openEditor('Move money, keep perspective','A paired transfer keeps both accounts in balance.',
    select('From account','from_account',accountOptions(state.data.accounts[0].id)) + select('To account','to_account',accountOptions(state.data.accounts[1].id)) + field('Amount ($)','amount','','number','step="0.01" min="0.01"') + field('Date','date',today(),'date') + field('Description','description','Account transfer','text','maxlength="240"',true) + '<p class="form-note">Creates a matching withdrawal and deposit. Use this for a credit card payment or a move to savings. If both sides are already imported, categorize those entries as transfers instead of adding another pair.</p>',data => send('/api/transfers',{...data,from_account:Number(data.from_account),to_account:Number(data.to_account)}),'Save transfer');
}
function openBudget(category) {
  const budget = state.data.budgets.find(b => b.category === category);
  const categories = state.user.categories.filter(c => !['Transfer','Salary','Other income','Investment income'].includes(c));
  openEditor('Give your spending a plan',`A category limit for ${monthLabel(state.month)}.`,
    select('Category','category',options(categories,category || 'Groceries'),true,budget?'disabled':'') + field('Monthly limit ($)','amount',budget ? (budget.limit_cents/100).toFixed(2) : '','number','min="0" step="0.01"',true) + '<p class="form-note">Saving a category that already has a budget replaces that month’s limit. Budgets do not roll over automatically.</p>', data => send('/api/budgets',{...data,category:budget?budget.category:data.category,month:state.month},'PUT'));
}
async function handleAction(action,id) {
  if (action === 'account') return openAccount();
  if (action === 'edit-account') return openAccount(id);
  if (action === 'delete-account' && confirm('Remove this empty account? Accounts with transactions cannot be removed.')) { await send(`/api/accounts/${id}`,{},'DELETE'); await refresh(); toast('Account removed.'); }
  if (action === 'transaction') return openTransaction();
  if (action === 'edit-transaction') return openTransaction(id);
  if (action === 'transfer') return openTransfer();
  if (action === 'budget') return openBudget();
  if (action === 'edit-budget') return openBudget(id);
  if (action === 'import') return openImport();
  if (action === 'next' || action === 'previous') { state.page += action === 'next' ? 1 : -1; return render(); }
  if (action === 'delete-budget' && confirm(`Remove the ${id} budget for ${monthLabel(state.month)}?`)) { await send(`/api/budgets/${state.month}/${encodeURIComponent(id)}`,{},'DELETE'); await refresh(); toast('Budget removed.'); }
  if (action === 'delete-transaction') {
    const row = state.data.transactions.find(r => r.id === Number(id));
    if (row && confirm(row.transfer_group ? 'Delete both sides of this transfer?' : `Delete “${row.description}”?`)) { await send(`/api/transactions/${id}`,{},'DELETE'); await refresh(); toast('Transaction removed.'); }
  }
}

let imported = {text:'',inspection:null,preview:null,edits:new Map(),page:0};
function importSteps(stage) { return `<div class="import-steps"><span class="${stage===1?'active':''}">01 · Choose a file</span><span class="${stage===2?'active':''}">02 · Match columns</span><span class="${stage===3?'active':''}">03 · Review & save</span></div>`; }
function openImport() {
  if (!requireAccounts()) return;
  imported = {text:'',inspection:null,preview:null,edits:new Map(),page:0};
  $('#import-content').innerHTML = `${importSteps(1)}<label class="field">Import into account<select id="import-account">${accountOptions()}</select></label><br><div class="dropzone">${icon('upload')}<h3>Your statement, your starting point.</h3><p>Choose a CSV exported from your bank. Up to 3 MB or 10,000 rows.</p><input id="csv-file" type="file" accept=".csv,text/csv" aria-label="Choose CSV file"></div><p class="section-note">Files are sent only to the computer running novaFinance. No outside service is contacted. Import one account per file.</p><p class="form-error" id="import-error" role="alert"></p><div class="form-actions"><a href="/static/example-transactions.csv" download class="button quiet">Download sample</a><button class="button primary" id="inspect-file" disabled>Match columns ${icon('arrow')}</button></div>`;
  $('#import-dialog').showModal();
  $('#csv-file').addEventListener('change', () => { $('#inspect-file').disabled = !$('#csv-file').files.length; });
  $('#inspect-file').addEventListener('click', async event => {
    const button = event.currentTarget; button.disabled = true; $('#import-error').textContent = '';
    try {
      const file = $('#csv-file').files[0];
      if (!file || file.size > 3_000_000) throw new Error('Choose a CSV no larger than 3 MB.');
      const bytes = await file.arrayBuffer();
      try { imported.text = new TextDecoder('utf-8',{fatal:true}).decode(bytes); } catch { imported.text = new TextDecoder('windows-1252').decode(bytes); }
      imported.account_id = Number($('#import-account').value);
      imported.inspection = await send('/api/import/inspect',{text:imported.text});
      mappingStep();
    } catch (error) { $('#import-error').textContent = error.message; button.disabled = false; }
  });
}
function mappingStep() {
  const {headers,suggested,row_count,sample} = imported.inspection;
  // Banks often supply both a net amount and debit/credit; start with one explicit mode.
  const selected = imported.mapping || {...suggested};
  if (!imported.mapping && selected.amount) { selected.debit = ''; selected.credit = ''; }
  const labels = {date:'Date *',description:'Description *',amount:'Signed amount',debit:'Debit / money out',credit:'Credit / money in',category:'Category (optional)',external_id:'Transaction ID (optional)',kind:'Kind (optional)'};
  $('#import-content').innerHTML = `${importSteps(2)}<p class="form-note">${row_count.toLocaleString()} rows found. Select a signed amount column OR debit/credit columns. A positive signed amount must add to the account. Bank transaction IDs give the most reliable duplicate detection. Only map Kind if its values are income, expense, or transfer.</p><form id="mapping-form"><div class="mapping-grid">${Object.entries(labels).map(([key,label]) => `<label class="field">${label}<select name="${key}"><option value="">Not mapped</option>${options(headers,selected[key])}</select></label>`).join('')}<label class="field">Date format<select name="date_format">${[['%Y-%m-%d','YYYY-MM-DD'],['%m/%d/%Y','MM/DD/YYYY'],['%d/%m/%Y','DD/MM/YYYY'],['%m/%d/%y','MM/DD/YY']].map(([value,label])=>`<option value="${value}" ${value === imported.date_format?'selected':''}>${label}</option>`).join('')}</select></label></div><br><label class="check"><input type="checkbox" name="invert" ${imported.invert?'checked':''}>Reverse signed amounts (for files where purchases are positive)</label><div class="table-wrap" style="margin:18px 0"><table><thead><tr>${headers.map(h=>`<th>${escapeHTML(h)}</th>`).join('')}</tr></thead><tbody>${sample.map(row=>`<tr>${headers.map(h=>`<td>${escapeHTML(row[h])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="form-error" id="import-error" role="alert"></p><div class="form-actions"><button type="button" class="button" id="import-restart">Choose another file</button><button type="submit" class="button primary">Preview transactions ${icon('arrow')}</button></div></form>`;
  $('#import-restart').addEventListener('click', () => { $('#import-dialog').close(); openImport(); });
  $('#mapping-form').addEventListener('submit', async event => {
    event.preventDefault(); const button = $('[type=submit]',event.target); button.disabled = true; $('#import-error').textContent = '';
    try {
      const values = Object.fromEntries(new FormData(event.target));
      imported.date_format = values.date_format; imported.invert = values.invert === 'on';
      delete values.date_format; delete values.invert; imported.mapping = values;
      imported.preview = await send('/api/import/preview',{text:imported.text,account_id:imported.account_id,mapping:values,date_format:imported.date_format,invert:imported.invert});
      imported.edits = new Map(imported.preview.rows.map(r => [r.row,{row:r.row,include:!r.duplicate,category:r.category,kind:r.kind}])); imported.page = 0;
      reviewStep();
    } catch(error) { $('#import-error').textContent = error.message; button.disabled = false; }
  });
}
function reviewStep() {
  const p = imported.preview;
  $('#import-content').innerHTML = `${importSteps(3)}<div class="review-summary"><span>${p.new_count} new transactions</span><span>${p.duplicate_count} duplicates skipped</span>${p.errors.length ? `<span>${p.errors.length} rows need correction</span>` : ''}</div><p class="form-note">Review the amount signs, categories, and kind before saving. Mark payments between your own accounts as transfers; mark refunds as expenses. Duplicate rows are skipped. Without transaction IDs, identical transactions in overlapping files can be ambiguous.</p>${p.errors.length ? `<ul class="import-errors">${p.errors.map(e=>`<li>Row ${e.row}: ${escapeHTML(e.error)}</li>`).join('')}</ul><p class="section-note">No rows can be saved until all errors are corrected. Fix the CSV or change the mapping, then preview again.</p>` : ''}<div id="review-table"></div><p class="form-error" id="import-error" role="alert"></p><div class="form-actions"><button class="button" id="back-mapping">Back to columns</button><button class="button primary" id="commit-import" ${!p.draft_id || !p.new_count?'disabled':''}>${icon('check')}Save reviewed transactions</button></div>`;
  renderReviewRows();
  $('#back-mapping').addEventListener('click',mappingStep);
  $('#commit-import').addEventListener('click', async event => {
    const button = event.currentTarget; button.disabled = true; $('#import-error').textContent = '';
    try {
      const result = await send('/api/import/commit',{draft_id:p.draft_id,edits:[...imported.edits.values()]});
      $('#import-dialog').close(); imported.text = ''; await refresh(); toast(`${result.added} transactions imported. ${result.skipped} skipped.`);
    } catch(error) { if ($('#import-dialog').open) $('#import-error').textContent = error.message; else toast(error.message,true); button.disabled = false; }
  });
}
function renderReviewRows() {
  const rows = imported.preview.rows, page = imported.page, count = Math.max(1,Math.ceil(rows.length/50));
  $('#review-table').innerHTML = `<div class="import-review"><table><thead><tr><th>Include</th><th>Date</th><th>Description</th><th>Amount</th><th>Kind</th><th>Category</th></tr></thead><tbody>${rows.slice(page*50,(page+1)*50).map(r=>{const edit=imported.edits.get(r.row);return `<tr class="${r.duplicate?'duplicate':''}" data-row="${r.row}"><td><input type="checkbox" data-review="include" aria-label="Include row ${r.row}" ${edit.include?'checked':''} ${r.duplicate?'disabled':''}>${r.duplicate?'<small>Duplicate</small>':''}</td><td>${r.date}</td><td>${escapeHTML(r.description)}</td><td class="amount ${r.amount_cents>0?'inflow':''}">${currency(r.amount_cents)}</td><td><select data-review="kind" aria-label="Kind for row ${r.row}" ${r.duplicate?'disabled':''}>${options(['expense','income','transfer'],edit.kind)}</select></td><td><select data-review="category" aria-label="Category for row ${r.row}" ${r.duplicate?'disabled':''}>${options(state.user.categories,edit.category)}</select></td></tr>`;}).join('')}</tbody></table></div><div class="pagination"><span>Review page ${page+1} of ${count} · all pages are saved together</span><div class="actions"><button class="button" id="review-previous" ${page===0?'disabled':''}>Previous</button><button class="button" id="review-next" ${page+1>=count?'disabled':''}>Next</button></div></div>`;
  $('#review-previous').addEventListener('click',()=>{imported.page--;renderReviewRows();});
  $('#review-next').addEventListener('click',()=>{imported.page++;renderReviewRows();});
  $('#review-table').onchange = event=>{
    const target=event.target, key=target.dataset.review; if(!key)return;
    const row=target.closest('[data-row]'), edit=imported.edits.get(Number(row.dataset.row)); edit[key]=key==='include'?target.checked:target.value;
    if(key==='kind') { if(edit.kind==='transfer')edit.category='Transfer'; else if(edit.category==='Transfer')edit.category=edit.kind==='income'?'Other income':'Uncategorized'; $('[data-review=category]',row).value=edit.category; }
  };
}

(async () => { try { await enterWorkspace(); } catch(error) { showAuth(); if(error.message !== 'Sign in to continue.') toast(error.message,true); } })();
