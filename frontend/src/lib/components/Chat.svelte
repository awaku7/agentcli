<script>
  import Message from './Message.svelte';
  import { onMessage, getMessages, getRoomId } from '../../lib/stores.svelte.js';
  import { extractHtmlFromText } from '../../lib/utils.js';
  import { setArtifactHtml } from '../../lib/stores.svelte.js';

  let messages = $state([]);
  let roomId = $state('');
  $effect(() => { messages = getMessages(); });
  $effect(() => { roomId = getRoomId(); });
  let chatBox = $state(null);
  let streamState = $state({ id: null, active: false, done: false, text: '', reasoning: '' });
  let imageStreamState = $state({ src: '', mime: '', partial: false, visible: false });

  function scrollToBottom() {
    if (chatBox) requestAnimationFrame(() => {
      requestAnimationFrame(() => { chatBox.scrollTop = chatBox.scrollHeight; });
    });
  }

  // Scroll on new messages
  $effect(() => {
    if (messages.length) scrollToBottom();
  });

  // Scroll during streaming (text or reasoning)
  $effect(() => {
    if (streamState.text || streamState.reasoning) scrollToBottom();
  });



  // When new messages arrive from history (sync), clear completed bubble
  $effect(() => {
    if (messages.length > 0) {
      const last = messages[messages.length - 1];
      if (last?.role === 'assistant' && streamState.done) {
        streamState = { ...streamState, done: false };
      }
    }
  });

  // Scroll when stream ends
  $effect(() => {
    if (!streamState.active) scrollToBottom();
  });

  $effect(() => {
    const unsubStart = onMessage('streamStart', (id) => { streamState = { id, active: true, done: false, text: '', reasoning: '' }; });
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
    const unsubImage = onMessage('imageEvent', (data) => {
      if (!data?.data_base64) return;
      const mime = data.mime || 'image/png';
      const value = data.data_base64.startsWith('data:')
        ? data.data_base64
        : `data:${mime};base64,${data.data_base64}`;
      imageStreamState = {
        src: value,
        mime,
        partial: !data.is_final,
        visible: true,
      };
      scrollToBottom();
    });
    const unsubEnd = onMessage('streamEnd', (id) => {
      if (streamState.id === id) {
        const html = extractHtmlFromText(streamState.text);
        if (html) setArtifactHtml(html);
        // Keep bubble visible as completed message
        streamState = { ...streamState, active: false, done: true };
      }
    });
    return () => { unsubStart(); unsubDelta(); unsubReasoning(); unsubImage(); unsubEnd(); };
  });
</script>

<div
  bind:this={chatBox}
  class="chat-container overflow-y-auto surface-card rounded-xl p-4 flex-grow flex flex-col gap-3"
>
  {#each messages as msg, i (i)}
    <Message {msg} {roomId} />
  {/each}
  {#if (streamState.active || streamState.done) && (streamState.text || streamState.reasoning)}
    <div class="p-3 rounded-lg max-w-[85%] role-assistant shadow-sm msg-anim" class:opacity-60={streamState.done}>
      <strong>ASSISTANT:</strong>
      {#if streamState.reasoning}
        <pre class="mt-1 whitespace-pre-wrap font-mono text-xs" style="opacity:0.55;">{streamState.reasoning}</pre>
      {/if}
      {#if streamState.text}
        <pre class="mt-1 whitespace-pre-wrap font-mono text-sm">{streamState.text}</pre>
      {/if}
    </div>
  {/if}
  {#if imageStreamState.visible}
    <div class="p-3 rounded-lg max-w-[85%] role-assistant shadow-sm image-stream-bubble" class:opacity-60={imageStreamState.partial}>
      <strong>{imageStreamState.partial ? 'IMAGE PREVIEW:' : 'IMAGE:'}</strong>
      <img src={imageStreamState.src} alt="Generated image preview" class="image-stream-preview" />
    </div>
  {/if}
</div>

<style>
  .chat-container { min-height: 0; }
  .chat-container::-webkit-scrollbar { width: 6px; }
  .chat-container::-webkit-scrollbar-track { background: transparent; }
  .chat-container::-webkit-scrollbar-thumb { background: var(--text-muted); border-radius: 3px; }
  .opacity-60 { opacity: 0.6; }
  .image-stream-bubble { background: var(--surface); }
  .image-stream-preview { display: block; max-width: min(100%, 640px); max-height: 60vh; margin-top: 0.5rem; border-radius: 0.5rem; object-fit: contain; }
</style>
