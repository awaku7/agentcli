<script>
  import { t } from '../../lib/i18n.svelte.js';
  import { getCurrentArtifactHtml, setArtifactHtml } from '../../lib/stores.svelte.js';

  let mode = $state('preview');
  let visible = $derived(!!getCurrentArtifactHtml());
  let artifactHtml = $derived(getCurrentArtifactHtml());

  function close() {
    setArtifactHtml('');
  }
</script>

{#if visible && artifactHtml}
  <div class="w-[45%] surface-card rounded-xl flex flex-col border overflow-hidden shrink-0 hidden md:flex" style="background:var(--bg-surface);border-color:var(--border-color);">
    <div class="flex justify-between items-center px-4 py-3 border-b shrink-0" style="background:var(--bg-surface-alt);border-color:var(--border-color);">
      <span class="font-bold text-sm">{t('artifactPreview')}</span>
      <div class="flex gap-2">
        <button
          onclick={() => mode = 'preview'}
          class="px-3 py-1.5 text-xs rounded-lg font-bold text-white transition"
          style="background:{mode === 'preview' ? 'var(--accent)' : 'var(--border-color)'};color:{mode === 'preview' ? 'white' : 'var(--text-secondary)'};"
        >{t('preview')}</button>
        <button
          onclick={() => mode = 'code'}
          class="px-3 py-1.5 text-xs rounded-lg font-bold transition"
          style="background:{mode === 'code' ? 'var(--accent)' : 'var(--border-color)'};color:{mode === 'code' ? 'white' : 'var(--text-secondary)'};"
        >{t('code')}</button>
        <button onclick={close} class="text-lg leading-none px-1 transition hover:opacity-70" style="color:var(--text-muted);">×</button>
      </div>
    </div>
    <div class="flex-grow relative" style="background:var(--bg-surface-alt);">
      {#if mode === 'preview'}
        <iframe
          title="Artifact Preview"
          sandbox="allow-scripts"
          class="w-full h-full border-none"
          srcdoc={artifactHtml.includes('tailwindcss') ? artifactHtml : artifactHtml.replace('</head>', '<script src="https://cdn.tailwindcss.com"><\/script></head>')}
          style="background:var(--bg-surface);"
        ></iframe>
      {:else}
        <pre class="w-full h-full p-4 overflow-auto text-xs font-mono" style="background:#0f172a;color:#e2e8f0;">{artifactHtml}</pre>
      {/if}
    </div>
  </div>
{/if}
