// One-time startup-state read for the Web server, not per-room worker activity.
const descriptions = {
  ja: {
    ON: 'WebサーバーでMXC Sandboxは初期化済み（ページ表示時点）',
    OFF: 'WebサーバーでSandboxは無効（ページ表示時点）',
    UNKNOWN: 'Sandboxの起動状態を確認できません',
  },
  en: {
    ON: 'MXC Sandbox initialized for this Web server (page-load snapshot)',
    OFF: 'Sandbox disabled for this Web server (page-load snapshot)',
    UNKNOWN: 'Sandbox startup status unavailable',
  },
  ar: {
    ON: 'تمت تهيئة MXC Sandbox لخادم الويب (حالة وقت التحميل)',
    OFF: 'Sandbox معطّل لخادم الويب (حالة وقت التحميل)',
    UNKNOWN: 'تعذّر معرفة حالة تشغيل Sandbox',
  },
};
export function sandboxLabel(state) {
  return 'Sandbox: ' + (state === 'ON' || state === 'OFF' ? state : '?');
}
export function sandboxDescription(state, lang = 'en') {
  const locale = String(lang).split(/[_-]/)[0];
  const messages = descriptions[locale] || descriptions.en;
  return messages[state] || messages.UNKNOWN;
}
export function mountSandboxStatus() {
  const header = document.querySelector('#chat-pane .header');
  const actions = header?.lastElementChild;
  if (!actions) return false;
  if (actions.querySelector('[data-uag-sandbox-state]')) return true;
  const badge = document.createElement('span');
  badge.dataset.uagSandboxState = 'true';
  badge.setAttribute('role', 'status');
  badge.style.cssText = 'white-space:nowrap;font-size:11px;font-weight:600;padding:2px 6px;border-radius:5px;border:1px solid var(--border-color);color:var(--text-secondary);';
  actions.insertBefore(badge, actions.firstChild);
  function render(state) {
    badge.textContent = sandboxLabel(state);
    badge.title = sandboxDescription(state, document.documentElement.lang || 'en');
  }
  render('UNKNOWN');
  // Sandbox setup is fixed when the Web server starts; do not poll.
  fetch('/api/sandbox-status', { credentials: 'same-origin', cache: 'no-store' })
    .then(async (response) => {
      if (!response.ok) throw new Error('Sandbox status unavailable');
      return response.json();
    })
    .then((data) => render(data.ok === true ? data.state : 'UNKNOWN'))
    .catch(() => render('UNKNOWN'));
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
