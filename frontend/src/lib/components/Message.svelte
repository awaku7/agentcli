<script>
  import { extractHtmlFromText, formatMessageBody, normalizeToolMessage, escapeHtml } from '../../lib/utils.js';
  import { setArtifactHtml } from '../../lib/stores.svelte.js';
  import { t } from '../../lib/i18n.svelte.js';

  let { msg, roomId = '' } = $props();
  
  let role = $derived(String(msg.role || '').toLowerCase());
  let content = $derived(String(msg.content || ''));
  let name = $derived(String(msg.name || ''));

  let reasoningContent = $derived(msg.reasoning_content ? String(msg.reasoning_content) : '');
  let displayContent = $derived(role === 'tool' ? normalizeToolMessage(msg) : content);
  let formattedHtml = $derived(role === 'assistant' ? formatMessageBody(displayContent) : escapeHtml(displayContent));
  let artifactHtml = $derived(role === 'assistant' ? extractHtmlFromText(displayContent) : '');

  function openPreview() { if (artifactHtml) setArtifactHtml(artifactHtml); }

  function localFileUrl(path) {
    const params = new URLSearchParams({ path });
    if (roomId) params.set('room_id', roomId);
    return `/local-file?${params.toString()}`;
  }
</script>

{#if role !== 'system' && (role !== 'assistant' || displayContent.trim())}
  <div
    class="p-3 rounded-xl shadow-sm msg-anim"
    class:role-user={role === 'user'}
    class:role-assistant={role === 'assistant'}
    class:role-tool={role === 'tool'}
  >
    {#if role === 'user'}
      <div class="text-xs font-semibold mb-1 opacity-80">{t('you')}</div>
      <pre class="whitespace-pre-wrap font-medium" style="font-size:13.5px;line-height:1.6;">{displayContent}</pre>
    {:else if role === 'assistant'}
      <div class="text-xs font-semibold mb-2 flex items-center gap-1.5" style="color:var(--accent);">
        <span style="width:6px;height:6px;border-radius:50%;background:var(--accent);display:inline-block;"></span>
        {t('uagent')}
      </div>
      {#if reasoningContent}
        <pre class="whitespace-pre-wrap font-mono text-xs mb-2" style="opacity:0.55;">{reasoningContent}</pre>
      {/if}
      <div class="text-sm leading-relaxed whitespace-pre-wrap font-mono">{@html formattedHtml}</div>
      {#if artifactHtml}
        <button
          onclick={openPreview}
          class="mt-2 px-3 py-1.5 rounded-lg text-xs font-bold text-white shadow-sm transition hover:brightness-110 active:scale-[0.97] flex items-center gap-1"
          style="background:linear-gradient(135deg, var(--accent), #8b5cf6);"
        >✨ Preview</button>
      {/if}
    {:else if role === 'tool'}
      <pre class="whitespace-pre-wrap font-mono" style="font-size:11.5px;">{displayContent}</pre>
      {#if msg.attachments?.length}
        <div class="mt-2 flex flex-wrap gap-2">
          {#each msg.attachments as att}
            {@const path = att.saved_path || att.path || ''}
            {@const src = att.data_url || att.url || (path ? localFileUrl(path) : '')}
            {#if src && (att.type?.startsWith('image/') || /\.(png|jpe?g|gif|webp)$/i.test(path))}
              <button
                type="button"
                class="p-0 border-0 bg-transparent cursor-pointer"
                aria-label={att.name || 'Open image'}
                onclick={() => window.open(src, '_blank')}
              >
                <img
                  src={src}
                  alt={att.name || 'image'}
                  class="max-w-[200px] max-h-[140px] rounded-lg border transition hover:opacity-90"
                  style="border-color:var(--border-color);"
                />
              </button>
            {:else if src && (att.type?.startsWith('audio/') || /\.(mp3|wav|ogg)$/i.test(path))}
              <audio controls preload="none" class="w-[200px]" src={src}></audio>
            {:else}
              <a
                href={src}
                download={att.name || path.split(/[\\/]/).pop() || 'file'}
                target="_blank"
                rel="noreferrer"
                class="text-xs px-2 py-1 rounded underline hover:brightness-110"
                style="color:var(--accent);background:var(--bg-surface-alt);"
              >
                {att.name || path.split(/[\\/]/).pop() || 'file'} · {t('download', 'Download')}
              </a>
            {/if}
          {/each}
        </div>
      {/if}
    {/if}
  </div>
{/if}
