<script>
  import { t } from '../../lib/i18n.svelte.js';
  import { getStatus } from '../../lib/stores.svelte.js';

  let status = $derived(getStatus());
</script>

<div class="rounded-xl px-4 py-2.5 flex justify-between items-center text-sm shrink-0"
  style="background:var(--bg-surface);border:1px solid var(--border-color);box-shadow:var(--shadow-sm);">
  <span class="font-mono text-xs" style="color:var(--text-tertiary);">{t('status')}:</span>
  <span class="text-xs font-bold px-3 py-1 rounded-full"
    class:status-busy={status.busy} class:status-idle={!status.busy}
    style="background:{status.busy ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)'};">
    {status.label}
  </span>
</div>
