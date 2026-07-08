<script>
  import { t } from '../../lib/i18n.svelte.js';
  import { isImageAttachment, isAudioAttachment, basename } from '../../lib/utils.js';

  let { pendingAttachments = [], onClear, onRemove, onUpload } = $props();
  let dragOver = $state(false);

  function handleDragOver(e) { e.preventDefault(); dragOver = true; }
  function handleDragLeave() { dragOver = false; }
  function handleDrop(e) {
    e.preventDefault(); dragOver = false;
    if (e.dataTransfer?.files?.length) onUpload(e.dataTransfer.files);
  }
  function handleFilePick(e) {
    if (e.target?.files?.length) { onUpload(e.target.files); e.target.value = ''; }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="rounded-xl border-2 border-dashed p-3 transition-all"
  style="background:{dragOver ? 'var(--accent-subtle)' : 'var(--bg-surface-alt)'};border-color:{dragOver ? 'var(--accent)' : 'var(--border-color)'};"
  ondragover={handleDragOver} ondragleave={handleDragLeave} ondrop={handleDrop}
  role="region"
>
  <div class="flex items-center justify-between gap-2 mb-2">
    <span class="text-sm" style="color:var(--text-tertiary);">{t('dropFiles')}</span>
    <label class="text-sm px-3 py-1.5 rounded-lg cursor-pointer transition hover:opacity-80 font-medium" style="background:var(--bg-surface);color:var(--text-secondary);border:1px solid var(--border-color);">
      {t('chooseFiles')}
      <input type="file" multiple class="hidden" onchange={handleFilePick} />
    </label>
  </div>
  <div class="flex flex-wrap gap-3">
    {#if pendingAttachments.length === 0}
      <span class="text-xs" style="color:var(--text-tertiary);">{t('noAttachments')}</span>
    {:else}
      {#each pendingAttachments as att, i}
        {@const img = isImageAttachment(att) && (att.data_url || att.saved_path || att.path)}
        {@const audio = isAudioAttachment(att) && (att.saved_path || att.path)}
        <div class="relative inline-block max-w-[220px] rounded-lg overflow-hidden" style="border:1px solid var(--border-color);">
          <button
            onclick={() => onRemove?.(i)}
            class="absolute top-1 right-1 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold z-10 transition hover:scale-110"
            style="background:rgba(0,0,0,0.5);color:white;"
          >×</button>
          {#if img}
            <img src={att.data_url || `/local-file?path=${encodeURIComponent(att.saved_path || att.path)}`} alt={att.name || 'image'} class="max-w-[200px] max-h-[140px]" />
          {:else if audio}
            <audio controls preload="none" class="w-[200px]" src={`/local-file?path=${encodeURIComponent(att.saved_path || att.path)}`}></audio>
          {:else}
            <div class="p-2 text-xs" style="color:var(--text-secondary);">{att.name || basename(att.saved_path || att.path || '') || 'file'}</div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</div>
