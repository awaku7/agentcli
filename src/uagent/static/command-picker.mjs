// Browser-only command picker. Served unchanged by Vite and bundled UAG Web.
// The catalog is authorized by the server on every open, never hardcoded here.
const phrases = {
  ja: {button:'コマンド',search:'コマンドを検索',args:'引数（必要な場合）',run:'実行',close:'閉じる',loading:'取得中…',empty:'利用できるコマンドがありません',select:'コマンドを選択',sub:'サブコマンド',failed:'コマンドを実行できませんでした',sent:'実行しました',room:'ルームの接続を確認してください'},
  en: {button:'Command',search:'Search commands',args:'Arguments (optional)',run:'Run',close:'Close',loading:'Loading…',empty:'No available commands',select:'Select a command',sub:'Subcommand',failed:'Command failed',sent:'Command executed',room:'Connect to a room first'},
  ar: {button:'الأوامر',search:'ابحث عن أمر',args:'المعاملات (اختياري)',run:'تنفيذ',close:'إغلاق',loading:'جار التحميل…',empty:'لا توجد أوامر متاحة',select:'اختر أمراً',sub:'الأمر الفرعي',failed:'فشل تنفيذ الأمر',sent:'تم التنفيذ',room:'اتصل بالغرفة أولاً'},
};
function labels() {
  const language = document.documentElement.lang.split(/[_-]/)[0];
  return phrases[language] || phrases.en;
}
export function filterCommands(commands, query) {
  const term = String(query || '').trim().toLocaleLowerCase();
  return (commands || []).filter((command) =>
    !term || [command.name, command.summary, command.usage].some((value) =>
      String(value || '').toLocaleLowerCase().includes(term)
    )
  );
}
export function composeCommand(name, subcommand = '', argumentsText = '') {
  return ':' + String(name || '').trim()
    + (String(subcommand || '').trim() ? ' ' + String(subcommand).trim() : '')
    + (String(argumentsText || '').trim() ? ' ' + String(argumentsText).trim() : '');
}
function roomId() {
  const url = new URL(window.location.href);
  const value = (url.pathname.match(/^\/room\/([^/]+)/) || [])[1] || url.searchParams.get('room') || '';
  try { return decodeURIComponent(value); } catch { return ''; }
}
function element(tag, className, textValue) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (textValue !== undefined) node.textContent = textValue;
  return node;
}
export function mountCommandPicker() {
  const textarea = document.querySelector('#chat-pane textarea');
  const anchor = textarea?.parentElement;
  if (!anchor || anchor.querySelector('[data-uag-command-picker]')) return !!anchor;
  const l = labels();
  const wrapper = element('div', 'uag-command-picker');
  wrapper.dataset.uagCommandPicker = 'true';
  const toggle = element('button', 'uag-command-toggle', '⌘ ' + l.button);
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-haspopup', 'dialog');
  const panel = element('div', 'uag-command-panel');
  panel.hidden = true;
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', l.button);
  const heading = element('div', 'uag-command-heading', l.select);
  const close = element('button', 'uag-command-close', '×');
  close.type = 'button';
  close.setAttribute('aria-label', l.close);
  heading.append(close);
  const search = element('input', 'uag-command-search');
  search.type = 'search';
  search.placeholder = l.search;
  search.setAttribute('aria-label', l.search);
  const list = element('div', 'uag-command-list');
  const chosen = element('div', 'uag-command-chosen');
  chosen.hidden = true;
  const selectedLabel = element('div', 'uag-command-selected');
  const selectedUsage = element('div', 'uag-command-usage');
  const subSelect = element('select', 'uag-command-select');
  subSelect.setAttribute('aria-label', l.sub);
  subSelect.hidden = true;
  const args = element('input', 'uag-command-args');
  args.type = 'text';
  args.placeholder = l.args;
  args.setAttribute('aria-label', l.args);
  const execute = element('button', 'uag-command-execute', l.run);
  execute.type = 'button';
  const feedback = element('div', 'uag-command-feedback');
  feedback.setAttribute('role', 'status');
  feedback.setAttribute('aria-live', 'polite');
  chosen.append(selectedLabel, selectedUsage, subSelect, args, execute);
  panel.append(heading, search, list, chosen, feedback);
  wrapper.append(toggle, panel);
  // Keep this next to Send/Stop without requiring a Svelte rebuild.
  anchor.insertBefore(wrapper, anchor.lastElementChild);

  let catalog = [];
  let selected = null;
  let requestSerial = 0;
  function showError(message) { feedback.textContent = message; }
  function render() {
    list.replaceChildren();
    const matches = filterCommands(catalog, search.value);
    if (!matches.length) list.append(element('div', 'uag-command-empty', l.empty));
    for (const command of matches) {
      const row = element('button', 'uag-command-item');
      row.type = 'button';
      const title = element('span', 'uag-command-name', ':' + command.name);
      const summary = element('span', 'uag-command-summary', command.summary || command.usage || '');
      row.append(title, summary);
      row.addEventListener('click', () => choose(command));
      list.append(row);
    }
  }
  function choose(command) {
    selected = command;
    chosen.hidden = false;
    feedback.textContent = '';
    selectedLabel.textContent = ':' + command.name;
    selectedUsage.textContent = command.usage || '';
    subSelect.replaceChildren();
    const subcommands = (command.subcommands || []).filter((item) => item.name);
    subSelect.hidden = subcommands.length === 0;
    if (subcommands.length) {
      const blank = element('option', '', l.sub);
      blank.value = '';
      subSelect.append(blank);
      for (const sub of subcommands) {
        const option = element('option', '', sub.name + (sub.summary ? ' — ' + sub.summary : ''));
        option.value = sub.name;
        subSelect.append(option);
      }
    }
    args.value = '';
    args.focus();
  }
  function hide() {
    panel.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
    requestSerial++;
  }
  toggle.addEventListener('click', async () => {
    if (!panel.hidden) { hide(); return; }
    panel.hidden = false;
    toggle.setAttribute('aria-expanded', 'true');
    search.value = '';
    chosen.hidden = true;
    selected = null;
    catalog = [];
    list.replaceChildren(element('div', 'uag-command-empty', l.loading));
    feedback.textContent = '';
    const id = roomId();
    if (!id) { showError(l.room); return; }
    const serial = ++requestSerial;
    try {
      const response = await fetch('/api/commands?room_id=' + encodeURIComponent(id) +
        '&lang=' + encodeURIComponent(document.documentElement.lang || 'en'),
        { credentials: 'same-origin', cache: 'no-store' });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || String(response.status));
      if (serial !== requestSerial || panel.hidden) return;
      catalog = data.commands || [];
      render();
      search.focus();
    } catch (error) {
      if (serial !== requestSerial || panel.hidden) return;
      list.replaceChildren();
      showError(l.failed + ': ' + error.message);
    }
  });
  search.addEventListener('input', render);
  close.addEventListener('click', hide);
  execute.addEventListener('click', async () => {
    if (!selected) return;
    const id = roomId();
    if (!id) { showError(l.room); return; }
    execute.disabled = true;
    feedback.textContent = '';
    try {
      const response = await fetch('/api/command', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_id: id,
          command: composeCommand(selected.name, subSelect.hidden ? '' : subSelect.value, args.value),
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || String(response.status));
      hide();
    } catch (error) {
      showError(l.failed + ': ' + error.message);
    } finally {
      execute.disabled = false;
    }
  });
  panel.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { event.preventDefault(); hide(); toggle.focus(); }
  });
  document.addEventListener('pointerdown', (event) => {
    if (!wrapper.contains(event.target) && !panel.hidden) hide();
  });
  return true;
}
if (typeof document !== 'undefined') {
  function start() {
    if (mountCommandPicker()) return;
    const observer = new MutationObserver(() => {
      if (mountCommandPicker()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
}
