<script>
  import { t } from '../../lib/i18n.svelte.js';

  let { message = '', isPassword = false, onSubmit } = $props();
  let reply = $state('');

  function submit() {
    const v = (reply || '').trim();
    // Empty submit is ignored (server also ignores). Use explicit skip via "n".
    if (!v) return;
    if (onSubmit) onSubmit(v);
    reply = '';
  }
  function skip() {
    if (onSubmit) onSubmit('n');
    reply = '';
  }
  function handleKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      submit();
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 flex items-center justify-center z-50"
  style="background:rgba(0,0,0,0.6);backdrop-filter:blur(8px);"
  role="dialog"
  tabindex="-1"
>
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions a11y_no_static_element_interactions -->
  <div
    class="rounded-2xl shadow-2xl max-w-lg w-full mx-4 p-6"
    style="background:var(--bg-surface);border:1px solid var(--border-color);"
    role="document"
  >
    <h2 class="text-lg font-bold mb-2" style="background:linear-gradient(135deg, var(--accent), #8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">
      {t('humanAskTitle')}
    </h2>
    <div class="mb-4 text-sm whitespace-pre-wrap" style="color:var(--text-secondary);">{message}</div>
    <input
      type={isPassword ? 'password' : 'text'}
      bind:value={reply}
      onkeydown={handleKeydown}
      class="w-full p-3 border-0 rounded-xl mb-4 focus:outline-none transition font-medium"
      style="background:var(--bg-surface-alt);color:var(--text-primary);box-shadow:inset 0 2px 4px rgba(0,0,0,0.04), 0 0 0 1px var(--border-color);"
      placeholder={t('humanAskPlaceholder')}
    />
    <div class="flex justify-end gap-2">
      <button
        onclick={skip}
        class="px-4 py-2.5 rounded-xl text-sm font-bold shadow-sm transition hover:brightness-110 active:scale-[0.97]"
        style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);"
      >Skip</button>
      <button
        onclick={submit}
        class="px-6 py-2.5 rounded-xl text-sm font-bold text-white shadow-sm transition hover:brightness-110 active:scale-[0.97]"
        style="background:linear-gradient(135deg, var(--accent), #8b5cf6);"
      >{t('humanAskSubmit')} →</button>
    </div>
  </div>
</div>
