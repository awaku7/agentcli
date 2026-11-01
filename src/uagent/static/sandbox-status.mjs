// Lightweight Sandbox worker indicator for both development and packaged Web.
// Only an authenticated, room-authorized server response determines its state.
const descriptions = {
  ja: {
    OFF: 'Sandbox無効（Remoteのホストツール実行は許可されません）',
    READY: 'MXC初期化済み・このルームの隔離ワーカーは未起動または停止中',
    RUNNING: 'このルームの隔離ワーカープロセスが稼働中（待機中を含む）',
    UNKNOWN: 'Sandboxの状態を確認できません',
  },
  en: {
    OFF: 'Sandbox disabled (Remote host tools remain blocked)',
    READY: 'MXC initialized; no live isolated worker for this room',
    RUNNING: 'Isolated room worker process is alive (including idle)',
    UNKNOWN: 'Sandbox status unavailable',
  },
  ar: {
    OFF: 'وضع العزل معطّل',
    READY: 'MXC جاهز، ولا توجد عملية عزل نشطة لهذه الغرفة',
    RUNNING: 'عملية العزل لهذه الغرفة قيد التشغيل (قد تكون خاملة)',
    UNKNOWN: 'تعذّر معرفة حالة العزل',
  },
};
export function sandboxLabel(state) {
  const safe = ['OFF', 'READY', 'RUNNING'].includes(state) ? state : 'UNKNOWN';
  return 'Sandbox: ' + (safe === 'UNKNOWN' ? '?' : safe);
}
export function sandboxDescription(state, lang = 'en') {
  const locale = String(lang).split(/[_-]/)[0];
  return (descriptions[locale] || descriptions.en)[state] ||
    (descriptions[locale] || descriptions.en).UNKNOWN;
}
function roomId() {
  const url = new URL(window.location.href);
  const value = (url.pathname.match(/^\/room\/([^/]+)/) || [])[1] ||
    url.searchParams.get('room') || '';
  try { return decodeURIComponent(value); } catch { return ''; }
}
export function mountSandboxStatus() {
  const header = document.querySelector('#chat-pane .header');
  const actions = header?.lastElementChild;
  if (!actions) return false;
  if (actions.querySelector('[data-uag-sandbox-state]')) return true;
  const badge = document.createElement('span');
  badge.dataset.uagSandboxState = 'true';
  badge.setAttribute('role', 'status');
  badge.setAttribute('aria-live', 'polite');
  badge.style.cssText = 'white-space:nowrap;font-size:11px;font-weight:600;padding:2px 6px;border-radius:5px;border:1px solid var(--border-color);color:var(--text-secondary);';
  actions.insertBefore(badge, actions.firstChild);
  let requestVersion = 0;
  function render(state) {
    badge.textContent = sandboxLabel(state);
    badge.title = sandboxDescription(state, document.documentElement.lang || 'en') + ' (snapshot)';
  }
  async function refresh() {
    const version = ++requestVersion;
    const id = roomId();
    if (!id) { render('UNKNOWN'); return; }
    try {
      const response = await fetch('/api/rooms/' + encodeURIComponent(id) + '/sandbox-status',
        { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) throw new Error('Sandbox status unavailable');
      const data = await response.json();
      if (version !== requestVersion || id !== roomId()) return;
      render(data.ok === true ? data.state : 'UNKNOWN');
    } catch (_) {
      if (version === requestVersion && id === roomId()) render('UNKNOWN');
    }
  }
  render('UNKNOWN');
  // One snapshot per page load, after the server-issued room appears in the URL.
  // A newly created private room may not exist when the header first mounts.
  if (roomId()) {
    refresh();
  } else {
    const pendingRoom = new MutationObserver(() => {
      if (!roomId()) return;
      pendingRoom.disconnect();
      refresh();
    });
    pendingRoom.observe(header, { childList: true, subtree: true, characterData: true });
  }
  return true;
}
if (typeof document !== 'undefined') {
  function start() {
    if (mountSandboxStatus()) return;
    const observer = new MutationObserver(() => {
      if (mountSandboxStatus()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else start();
}
