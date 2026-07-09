<script>
  import { t } from '../../lib/i18n.svelte.js';
  import { getStatus, getInputHistory } from '../../lib/stores.svelte.js';

  let { onSend, onInterrupt, onCommand, pendingAttachments = [] } = $props();

  let text = $state('');
  let histIdx = $state(-1);

  let status = $derived(getStatus());
  let inputHistory = $derived(getInputHistory());
  let isBusy = $derived(status.busy);

  function handleKeydown(e) {
    if (e.key === 'Enter' && e.ctrlKey && !isBusy) { e.preventDefault(); send(); return; }
    if (e.key === 'ArrowUp' && e.ctrlKey && inputHistory.length) {
      e.preventDefault();
      histIdx = histIdx <= 0 ? inputHistory.length - 1 : histIdx - 1;
      text = inputHistory[histIdx] || '';
      return;
    }
    if (e.key === 'ArrowDown' && e.ctrlKey && inputHistory.length) {
      e.preventDefault();
      histIdx = histIdx >= inputHistory.length - 1 ? inputHistory.length : histIdx + 1;
      text = inputHistory[histIdx] || '';
      return;
    }
  }

  function send() {
    const t = text.trim();
    if (!t) return;
    if (t.startsWith(':')) { onCommand(t); text = ''; histIdx = inputHistory.length; return; }
    onSend(t, pendingAttachments);
    text = '';
    histIdx = inputHistory.length;
  }
</script>

<div class="flex gap-2 shrink-0">
  <textarea
    bind:value={text}
    onkeydown={handleKeydown}
    rows="2"
    class="flex-grow p-3 border-0 rounded-xl shadow-sm resize-none focus:outline-none transition font-medium"
    style="background:var(--bg-surface);color:var(--text-primary);box-shadow:inset 0 2px 4px rgba(0,0,0,0.04), 0 0 0 1px var(--border-color);font-size:13.5px;line-height:1.5;"
    placeholder={t('inputPlaceholder')}
    disabled={isBusy}
  ></textarea>
  {#if isBusy}
    <button
      onclick={onInterrupt}
      class="px-5 py-2 rounded-xl font-bold text-white shadow-sm transition hover:brightness-110 active:scale-[0.97] flex items-center gap-1.5"
      style="background:linear-gradient(135deg, #ef4444, #dc2626);"
    >⬛ {t('stop')}</button>
  {:else}
    <button
      onclick={send}
      disabled={!text.trim()}
      class="px-6 py-2 rounded-xl font-bold text-white shadow-sm transition hover:brightness-110 active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
      style="background:linear-gradient(135deg, var(--accent), #8b5cf6);"
    >{t('send')} →</button>
  {/if}
</div>
