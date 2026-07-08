<script>
  import { t } from '../../lib/i18n.svelte.js';
  import { getStatus, getRoomId } from '../../lib/stores.svelte.js';

  let { panelOpen = false, onTogglePanel } = $props();
  let status = $derived(getStatus());

  let dark = $state(document.documentElement.classList.contains('dark'));

  function toggleDark() {
    dark = !dark;
    document.documentElement.classList.toggle('dark', dark);
    try { localStorage.setItem('uag-theme', dark ? 'dark' : 'light'); } catch (_) {}
  }

  $effect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => {
      const saved = (() => { try { return localStorage.getItem('uag-theme'); } catch(_) { return null; } })();
      if (!saved) {
        dark = e.matches;
        document.documentElement.classList.toggle('dark', dark);
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  });
</script>

<div
  class="rounded-xl px-5 py-3 flex items-center justify-between gap-3 shrink-0"
  style="background:var(--bg-surface);border:1px solid var(--border-color);box-shadow:var(--shadow-sm);"
>
  <div class="flex items-center gap-3 min-w-0">
    <h1
      class="text-lg font-bold tracking-tight shrink-0"
      style="background:linear-gradient(135deg, var(--accent), #8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
    >
      {t('title')}
    </h1>
    <span class="text-xs font-mono hidden sm:inline truncate" style="color:var(--text-tertiary);">
      {getRoomId()}
    </span>
    <span class="text-xs font-mono ml-2 px-1.5 py-0.5 rounded" style="color:var(--accent);background:var(--accent-subtle);">
      {status.workdir ? `workdir: ${status.workdir}` : ''}
    </span>
  </div>
  <div class="flex items-center gap-2 shrink-0">
    <span
      class="text-xs font-semibold px-2 py-0.5 rounded-full"
      class:status-idle={!status.busy} class:status-busy={status.busy}
      style="background:{status.busy ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)'};"
    >
      {status.label}
    </span>
    {#if status.busy}
      <span
        class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full"
        style="background:rgba(239,68,68,0.15);color:var(--status-busy);animation:uag-pulse 1.5s ease-in-out infinite;"
      >
        {t('toolRunning')}
      </span>
    {/if}
    <button
      onclick={onTogglePanel}
      class="w-9 h-9 rounded-xl flex items-center justify-center cursor-pointer transition hover:scale-110 active:scale-95 border text-lg"
      style="background:{panelOpen ? 'var(--accent-subtle)' : 'transparent'};border-color:{panelOpen ? 'var(--accent)' : 'var(--border-color)'};color:{panelOpen ? 'var(--accent)' : 'var(--text-secondary)'};"
      title="Settings & Commands"
    >⚙</button>
    <button
      onclick={toggleDark}
      class="w-9 h-9 rounded-xl flex items-center justify-center cursor-pointer transition hover:scale-110 active:scale-95 border"
      style="background:transparent;border-color:var(--border-color);color:var(--text-secondary);"
      title={t('darkMode')}
    >{dark ? '☀️' : '🌙'}</button>
  </div>
</div>
