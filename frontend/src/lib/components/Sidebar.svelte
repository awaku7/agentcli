<script>
  import { onMount } from 'svelte';
  import { t } from '../../lib/i18n.svelte.js';
  import { getRoomId, fetchLogs } from '../../lib/stores.svelte.js';

  let { onClose, onOpenPanel } = $props();
  let roomId = $derived(getRoomId());
  let sessions = $state([]);
  let loading = $state(false);
  let error = $state('');
  let query = $state('');
  let filteredSessions = $derived(sessions.filter((session) => {
    const text = `${session.summary || ''} ${session.name || ''} ${session.path || ''}`.toLowerCase();
    return !query.trim() || text.includes(query.trim().toLowerCase());
  }));

  async function loadSessions() {
    loading = true;
    error = '';
    try {
      const result = await fetchLogs(1, 30);
      if (result.ok === false) {
        error = 'セッション履歴を読み込めませんでした';
      } else {
        sessions = result.logs || [];
      }
    } catch (e) {
      error = 'セッション履歴を読み込めませんでした';
    } finally {
      loading = false;
    }
  }

  function openSession(path) {
    if (!path) return;
    window.dispatchEvent(new CustomEvent('uag-load-session', { detail: { path } }));
    onClose?.();
  }

  function newSession() {
    const id = crypto.randomUUID().slice(0, 8);
    window.location.href = `/room/${id}`;
  }

  function formatTime(ts) {
    if (!ts) return '';
    const date = new Date(typeof ts === 'number' ? ts * 1000 : ts);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  onMount(loadSessions);
</script>

<aside class="sidebar" aria-label="Navigation">
  <div class="sidebar-header">
    <div class="brand-mark">U</div>
    <div class="brand-copy">
      <div class="brand-name">UAGENT</div>
      <div class="brand-subtitle">AI workspace</div>
    </div>
    <button class="icon-button mobile-only" onclick={() => onClose?.()} aria-label="Close navigation">×</button>
  </div>

  <button class="new-session" onclick={newSession}>
    <span class="new-session-icon">+</span>
    <span>{t('newSession', '新しいセッション')}</span>
  </button>

  <div class="section-heading">
    <span>{t('sessionHistory', '過去のセッション')}</span>
    <button class="refresh-button" onclick={loadSessions} disabled={loading} aria-label="Refresh sessions">↻</button>
  </div>
  <label class="search-box">
    <span aria-hidden="true">⌕</span>
    <input bind:value={query} type="search" placeholder={t('searchSessions', 'セッションを検索')} aria-label={t('searchSessions', 'セッションを検索')} />
  </label>

  <div class="session-list">
    {#if loading && !sessions.length}
      <div class="empty-state">読み込み中…</div>
    {:else if error}
      <div class="empty-state error">{error}</div>
    {:else if filteredSessions.length}
      {#each filteredSessions as session}
        <button class="session-item" class:active={session.path?.includes(roomId)} onclick={() => openSession(session.path)} title={session.path || ''}>
          <span class="session-dot"></span>
          <span class="session-body">
            <span class="session-name">{session.summary || session.name || '無題のセッション'}</span>
            <span class="session-meta">{formatTime(session.mtime)}{session.size ? ` · ${Math.ceil(session.size / 1024)} KB` : ''}</span>
          </span>
        </button>
      {/each}
    {:else}
      <div class="empty-state">まだセッションがありません</div>
    {/if}
  </div>

  <div class="sidebar-footer">
    <button class="footer-action" onclick={() => onOpenPanel?.('settings')}>
      <span class="footer-icon">⚙</span><span>{t('settings')}</span>
    </button>
    <button class="footer-action" onclick={() => onOpenPanel?.('auto')}>
      <span class="footer-icon">⌁</span><span>{t('tabAuto')}</span>
    </button>
    <button class="footer-action" onclick={() => onOpenPanel?.('logs')}>
      <span class="footer-icon">▤</span><span>{t('tabLogs')}</span>
    </button>
    <button class="footer-action" onclick={() => onOpenPanel?.('mem')}>
      <span class="footer-icon">◆</span><span>{t('tabMemory')}</span>
    </button>
    <button class="footer-action" onclick={() => onOpenPanel?.('profile')}>
      <span class="footer-icon">◎</span><span>{t('tabProfile')}</span>
    </button>
    <div class="room-label">ROOM <span>{roomId}</span></div>
  </div>
</aside>

<style>
  .sidebar { width: 280px; height: 100%; flex: 0 0 280px; display: flex; flex-direction: column; padding: 18px 14px 14px; background: var(--bg-surface); border-right: 1px solid var(--border-color); color: var(--text-primary); }
  .sidebar-header { display: flex; align-items: center; gap: 10px; padding: 2px 8px 20px; }
  .brand-mark { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 10px; color: white; font-weight: 800; background: linear-gradient(135deg, var(--accent), #8b5cf6); }
  .brand-name { font-size: 14px; font-weight: 800; letter-spacing: .08em; }
  .brand-subtitle { color: var(--text-tertiary); font-size: 10px; margin-top: 1px; }
  .brand-copy { flex: 1; }
  .icon-button { border: 0; background: transparent; color: var(--text-secondary); font-size: 24px; cursor: pointer; }
  .new-session { width: 100%; display: flex; align-items: center; gap: 10px; padding: 11px 13px; border: 1px solid var(--accent); border-radius: 10px; color: var(--accent); background: var(--accent-subtle); font-weight: 700; cursor: pointer; transition: filter var(--transition), transform var(--transition); }
  .new-session:hover { filter: brightness(1.08); }
  .new-session:active { transform: scale(.98); }
  .new-session-icon { font-size: 20px; line-height: 14px; font-weight: 400; }
  .section-heading { display: flex; justify-content: space-between; align-items: center; padding: 23px 8px 8px; color: var(--text-tertiary); font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
  .refresh-button { border: 0; color: var(--text-tertiary); background: transparent; font-size: 18px; cursor: pointer; }
  .refresh-button:disabled { opacity: .4; }
  .search-box { display: flex; align-items: center; gap: 7px; margin: 0 6px 8px; padding: 8px 10px; border: 1px solid var(--border-color); border-radius: 9px; color: var(--text-tertiary); background: var(--bg-surface-alt); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .search-box input { width: 100%; min-width: 0; border: 0; outline: 0; color: var(--text-primary); background: transparent; font-size: 11px; }
  .search-box input::placeholder { color: var(--text-tertiary); }
  .session-list { min-height: 0; flex: 1; overflow-y: auto; }
  .session-item { width: 100%; display: flex; gap: 9px; align-items: flex-start; padding: 10px 8px; border: 0; border-radius: 9px; text-align: left; color: var(--text-primary); background: transparent; cursor: pointer; transition: background var(--transition); }
  .session-item { transition: background var(--transition), transform var(--transition); }
  .session-item:hover, .session-item.active { background: var(--bg-surface-hover); }
  .session-item:hover { transform: translateX(2px); }
  .session-dot { width: 6px; height: 6px; flex: 0 0 6px; margin-top: 6px; border-radius: 50%; background: var(--text-tertiary); }
  .session-item.active .session-dot { background: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .session-body { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .session-name { overflow: hidden; font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
  .session-meta { color: var(--text-tertiary); font-size: 10px; }
  .empty-state { padding: 20px 8px; color: var(--text-tertiary); font-size: 11px; text-align: center; }
  .empty-state.error { color: var(--status-busy); }
  .sidebar-footer { padding-top: 12px; border-top: 1px solid var(--border-color); }
  .footer-action { width: 100%; display: flex; gap: 10px; align-items: center; padding: 9px 8px; border: 0; border-radius: 8px; color: var(--text-secondary); background: transparent; font-size: 12px; font-weight: 600; text-align: left; cursor: pointer; }
  .footer-action:hover { color: var(--text-primary); background: var(--bg-surface-hover); }
  .footer-icon { width: 18px; color: var(--accent); text-align: center; }
  .room-label { padding: 12px 8px 0; color: var(--text-tertiary); font: 10px/1.4 'JetBrains Mono', monospace; }
  .room-label span { color: var(--text-secondary); }
  .mobile-only { display: none; }
  @media (max-width: 768px) {
    .sidebar { position: fixed; inset: 0 auto 0 0; z-index: 40; width: min(280px, 86vw); box-shadow: var(--shadow-lg); }
    .mobile-only { display: block; }
  }
</style>
