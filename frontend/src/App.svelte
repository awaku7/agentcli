<script>
  import { onMount } from 'svelte';
  import Header from './lib/components/Header.svelte';
  import Chat from './lib/components/Chat.svelte';
  import InputArea from './lib/components/InputArea.svelte';
  import Attachments from './lib/components/Attachments.svelte';
  import StatusBar from './lib/components/StatusBar.svelte';
  import HumanAsk from './lib/components/HumanAsk.svelte';
  import PreviewPanel from './lib/components/PreviewPanel.svelte';
  import UnifiedPanel from './lib/components/UnifiedPanel.svelte';
  import {
    connect, getHumanAskState, getPendingAttachments,
    sendUserInput, sendCommand, sendInterrupt, sendHumanAskResponse,
    uploadFiles, fetchGenres,
    addAttachments, clearAttachments, removeAttachment,
  } from './lib/stores.svelte.js';
  import { setLang, detectLang } from './lib/i18n.svelte.js';

  let panelOpen = $state(false);

  let humanAskState = $derived(getHumanAskState());
  let pendingAttachments = $derived(getPendingAttachments());

  onMount(() => {
    setLang(detectLang());
    connect();
    fetchGenres();
    function handleKey(e) {
      if (e.key === 'Escape') panelOpen = false;
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  });

  function handleSend(text, attachments) {
    sendUserInput(text, attachments || []);
  }
  function handleInterrupt() { sendInterrupt(); }
  function handleCommand(cmd) { sendCommand(cmd); }
  function handleHumanAsk(text) { sendHumanAskResponse(text, humanAskState.isPassword); }
  async function handleFiles(files) {
    try {
      const uploaded = await uploadFiles(files);
      if (uploaded.length) addAttachments(uploaded);
    } catch (err) { console.error('Upload failed:', err); }
  }
</script>

<div class="h-screen w-screen flex overflow-hidden">
  <div id="chat-pane" class="flex-grow flex flex-col h-full p-4 gap-3 min-w-0" style="gap:0.75rem;">
    <Header onTogglePanel={() => panelOpen = !panelOpen} {panelOpen} />

    <Chat />

    <StatusBar />

    <Attachments
      {pendingAttachments}
      onClear={clearAttachments}
      onRemove={removeAttachment}
      onUpload={handleFiles}
    />

    <InputArea
      onSend={handleSend}
      onInterrupt={handleInterrupt}
      onCommand={handleCommand}
    />
  </div>

  <PreviewPanel />

  {#if panelOpen}
    <UnifiedPanel onClose={() => panelOpen = false} />
  {/if}

  {#if humanAskState.visible}
    <HumanAsk
      message={humanAskState.message}
      isPassword={humanAskState.isPassword}
      onSubmit={handleHumanAsk}
    />
  {/if}
</div>

<style>
  :global(.role-user) {
    background: var(--user-bubble) !important;
    color: var(--user-text) !important;
    align-self: flex-end;
    border-bottom-right-radius: 4px !important;
    border: none !important;
  }
  :global(.role-assistant) {
    background: var(--assistant-bubble) !important;
    color: var(--assistant-text) !important;
    align-self: flex-start;
    border-bottom-left-radius: 4px !important;
    border: 1px solid var(--border-color);
  }
  :global(.role-tool) {
    background: var(--tool-bg) !important;
    color: var(--text-primary) !important;
    font-size: 0.8rem;
    border-left: 3px solid var(--tool-border);
    margin: 4px 0;
    padding: 6px 10px !important;
    border-radius: 6px !important;
    max-width: 100% !important;
  }
  :global(.status-busy) { color: var(--status-busy); }
  :global(.status-idle) { color: var(--status-idle); }
  :global(.msg-anim) { animation: uag-msgIn 0.25s ease-out; }

  @media (max-width: 768px) {
    :global(#chat-pane) { padding: 0.5rem; }
  }
</style>
