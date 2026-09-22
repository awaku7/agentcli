<script>
  import { t } from '../../lib/i18n.svelte.js';
  import { getStatus, getInputHistory } from '../../lib/stores.svelte.js';

  let { onSend, onInterrupt, onCommand, pendingAttachments = [] } = $props();

  let text = $state('');
  let histIdx = $state(-1);
  let completionCandidates = $state([]);
  let completionIndex = $state(-1);

  const completionCommands = [
    ':auto',
    ':cd',
    ':clean',
    ':clear',
    ':cont',
    ':cp',
    ':env',
    ':exit',
    ':h',
    ':head',
    ':help',
    ':history',
    ':load',
    ':logs',
    ':ls',
    ':mem-del',
    ':mem-list',
    ':mem-vacuum',
    ':model',
    ':mv',
    ':plugin',
    ':profile',
    ':profile-clear',
    ':profile-fromlog',
    ':profile-show',
    ':quit',
    ':r',
    ':reasoning',
    ':redo',
    ':reload',
    ':replay',
    ':response',
    ':rm',
    ':save',
    ':sessions',
    ':shrink',
    ':shrink_llm',
    ':skills',
    ':tail',
    ':tool',
    ':tools',
    ':tokens',
    ':undo',
    ':v',
    ':verbosity',
    ':?',
  ];

  let status = $derived(getStatus());
  let inputHistory = $derived(getInputHistory());
  let isBusy = $derived(status.busy);

  function findCompletionCandidates(value) {
    const prefix = value.trimStart().toLowerCase();
    if (!prefix.startsWith(':') || /\s/.test(prefix)) return [];
    return completionCommands.filter((command) => command.startsWith(prefix));
  }

  function applyCompletion(candidate) {
    text = `${candidate} `;
    histIdx = inputHistory.length;
    completionCandidates = [];
    completionIndex = -1;
  }

  function handleInput() {
    completionCandidates = [];
    completionIndex = -1;
  }

  function handleKeydown(e) {
    if (e.ctrlKey && e.code === 'Space' && !isBusy) {
      e.preventDefault();
      const candidates = findCompletionCandidates(text);
      if (!candidates.length) {
        completionCandidates = [];
        completionIndex = -1;
        return;
      }
      completionCandidates = candidates;
      completionIndex = (completionIndex + 1) % completionCandidates.length;
      return;
    }
    if (completionCandidates.length && e.key === 'ArrowDown') {
      e.preventDefault();
      completionIndex = (completionIndex + 1) % completionCandidates.length;
      return;
    }
    if (completionCandidates.length && e.key === 'ArrowUp') {
      e.preventDefault();
      completionIndex =
        (completionIndex - 1 + completionCandidates.length) % completionCandidates.length;
      return;
    }
    if (completionCandidates.length && e.key === 'Enter' && !e.ctrlKey) {
      e.preventDefault();
      applyCompletion(completionCandidates[completionIndex]);
      return;
    }
    if (completionCandidates.length && e.key === 'Escape') {
      e.preventDefault();
      completionCandidates = [];
      completionIndex = -1;
      return;
    }
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
    completionCandidates = [];
    completionIndex = -1;
    const t = text.trim();
    if (!t) return;
    if (t.startsWith(':')) { onCommand(t); text = ''; histIdx = inputHistory.length; return; }
    onSend(t, pendingAttachments);
    text = '';
    histIdx = inputHistory.length;
  }
</script>

<div class="relative flex gap-2 shrink-0">
  {#if completionCandidates.length}
    <div
      class="absolute bottom-full left-0 z-20 mb-2 max-h-48 min-w-48 max-w-full overflow-auto rounded-xl p-1 shadow-lg"
      style="background:var(--bg-surface);border:1px solid var(--border-color);"
      role="listbox"
      aria-label="Command completion candidates"
    >
      {#each completionCandidates as candidate, index}
        <button
          type="button"
          class="block w-full rounded-lg px-3 py-1.5 text-left text-sm"
          class:bg-violet-100={index === completionIndex}
          style="color:var(--text-primary)"
          role="option"
          aria-selected={index === completionIndex}
          onclick={() => applyCompletion(candidate)}
        >{candidate}</button>
      {/each}
    </div>
  {/if}
  <textarea
    bind:value={text}
    onkeydown={handleKeydown}
    oninput={handleInput}
    rows="2"
    class="flex-grow p-3 border-0 rounded-xl shadow-sm resize-none focus:outline-none transition font-medium"
    style="background:var(--bg-surface);color:var(--text-primary);box-shadow:inset 0 2px 4px rgba(0,0,0,0.04), 0 0 0 1px var(--border-color);font-size:13.5px;line-height:1.5;"
    placeholder={t('inputPlaceholder')}
    aria-autocomplete="list"
    aria-keyshortcuts="Control+Space"
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
