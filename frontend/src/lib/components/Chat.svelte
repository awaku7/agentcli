<script>
  import Message from './Message.svelte';
  import { onMessage } from '../../lib/stores.svelte.js';
  import { extractHtmlFromText } from '../../lib/utils.js';
  import { setArtifactHtml } from '../../lib/stores.svelte.js';

  let { messages = [] } = $props();
  let chatBox = $state(null);
  let streamState = $state({ id: null, active: false, text: '', reasoning: '' });

  function scrollToBottom() {
    if (chatBox) requestAnimationFrame(() => { chatBox.scrollTop = chatBox.scrollHeight; });
  }

  // Scroll on new messages
  $effect(() => {
    if (messages.length) scrollToBottom();
  });

  // Scroll during streaming
  $effect(() => {
    if (streamState.text) scrollToBottom();
  });

  $effect(() => {
    const unsubStart = onMessage('streamStart', (id) => { streamState = { id, active: true, text: '', reasoning: '' }; });
    const unsubDelta = onMessage('streamDelta', (id, delta) => {
      if (streamState.active && streamState.id === id) {
        const newText = streamState.text + delta;
        streamState = { ...streamState, text: newText };
        // Auto-update preview panel during streaming
        const html = extractHtmlFromText(newText);
        if (html) setArtifactHtml(html);
      }
    });
    const unsubReasoning = onMessage('reasoning', (content) => {
      if (streamState.active) {
        streamState = { ...streamState, reasoning: streamState.reasoning + content };
      }
    });
    const unsubEnd = onMessage('streamEnd', (id) => {
      if (streamState.id === id) {
        // Final auto-update with complete text
        const html = extractHtmlFromText(streamState.text);
        if (html) setArtifactHtml(html);
        streamState = { id: null, active: false, text: '' };
      }
    });
    return () => { unsubStart(); unsubDelta(); unsubReasoning(); unsubEnd(); };
  });
</script>

<div
  bind:this={chatBox}
  class="chat-container overflow-y-auto surface-card rounded-xl p-4 flex-grow flex flex-col gap-3"
>
  {#each messages as msg, i (i)}
    <Message {msg} />
  {/each}
  {#if streamState.active && (streamState.text || streamState.reasoning)}
    <div class="p-3 rounded-lg max-w-[85%] role-assistant shadow-sm msg-anim">
      <strong>ASSISTANT:</strong>
      {#if streamState.reasoning}
        <pre class="mt-1 whitespace-pre-wrap font-mono text-xs" style="opacity:0.55;">{streamState.reasoning}</pre>
      {/if}
      {#if streamState.text}
        <pre class="mt-1 whitespace-pre-wrap font-mono text-sm">{streamState.text}</pre>
      {/if}
    </div>
  {/if}
</div>

<style>
  .chat-container { min-height: 0; }
  .chat-container::-webkit-scrollbar { width: 6px; }
  .chat-container::-webkit-scrollbar-track { background: transparent; }
  .chat-container::-webkit-scrollbar-thumb { background: var(--text-muted); border-radius: 3px; }
</style>
