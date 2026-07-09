const _state = $state({
  ws: null,
  connected: false,
  roomId: '',
  messages: [],
  status: { busy: false, label: 'IDLE', workdir: '' },
  modes: { reasoning: 'off', verbosity: 'off' },
  webVerbose: false,
  inputHistory: [],
  historyIndex: 0,
  pendingAttachments: [],
  currentArtifactHtml: '',
  currentToolHtml: '',
  _pendingStreamMsg: false,
  humanAskState: { visible: false, message: '', isPassword: false, resolve: null },
  genresEnabled: {},
});

// Reactive getters
export function getWs() { return _state.ws; }
export function getConnected() { return _state.connected; }
export function getRoomId() { return _state.roomId; }
export function getMessages() { return _state.messages; }
export function getStatus() { return _state.status; }
export function getModes() { return _state.modes; }
export function getWebVerbose() { return _state.webVerbose; }
export function getInputHistory() { return _state.inputHistory; }
export function getPendingAttachments() { return _state.pendingAttachments; }
export function getCurrentArtifactHtml() { return _state.currentArtifactHtml; }
export function getCurrentToolHtml() { return _state.currentToolHtml; }
export function getHumanAskState() { return _state.humanAskState; }
export function getGenresEnabled() { return _state.genresEnabled; }

// Setters (mutate properties rather than reassign)
export function setWs(v) { _state.ws = v; }
export function setConnected(v) { _state.connected = v; }
export function setRoomId(v) { _state.roomId = v; }
export function setMessages(v) { _state.messages = v; }
export function setStatus(v) { _state.status = v; }
export function setModes(v) { _state.modes = v; }
export function setWebVerbose(v) { _state.webVerbose = v; }
export function setInputHistory(v) { _state.inputHistory = v; }
export function setHistoryIndex(v) { _state.historyIndex = v; }
export function setPendingAttachments(v) { _state.pendingAttachments = v; }
export function setCurrentArtifactHtml(v) { _state.currentArtifactHtml = v; }
export function setHumanAskState(v) { _state.humanAskState = v; }

// Convenience functions
export function setArtifactHtml(html) { _state.currentArtifactHtml = html; }
export function pushAssistantMessage(text, reasoning) {
  _state._pendingStreamMsg = true;
  _state.messages = [..._state.messages, { role: 'assistant', content: text, reasoning_content: reasoning || '' }];
}
export function addAttachments(files) { _state.pendingAttachments = [..._state.pendingAttachments, ...files]; }
export function removeAttachment(index) { _state.pendingAttachments = _state.pendingAttachments.filter((_, i) => i !== index); }
export function clearAttachments() { _state.pendingAttachments = []; }

let reconnectTimer = null;
let messageHandlers = {};

export function getRoomIdFromUrl() {
  try {
    const url = new URL(window.location.href);
    const pathRoom = (url.pathname.match(/^\/room\/([^\/]+)/) || [])[1];
    const queryRoom = url.searchParams.get('room');
    return pathRoom || queryRoom || '';
  } catch (_) { return ''; }
}

export function connect() {
  const ws = _state.ws;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const room = getRoomIdFromUrl();
  _state.roomId = room || crypto.randomUUID().slice(0, 8);
  history.replaceState(null, '', '/room/' + _state.roomId);
  const lang = document.documentElement.lang || 'en';
  const qs = `?room=${encodeURIComponent(_state.roomId)}&lang=${encodeURIComponent(lang)}`;
  const newWs = new WebSocket(protocol + '//' + window.location.host + '/ws' + qs);

  newWs.onopen = () => {
    _state.connected = true;
    _state.ws = newWs;
  };

  newWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleWsMessage(data);
  };

  newWs.onclose = () => {
    _state.connected = false;
    _state.ws = null;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => connect(), 2000);
  };

  newWs.onerror = () => {
    newWs.close();
  };
}

function handleWsMessage(data) {
  switch (data.type) {
    case 'init':
      _state.messages = data.messages || [];
      _state.inputHistory = data.input_history || [];
      _state.historyIndex = _state.inputHistory.length;
      _state.webVerbose = !!data.web_verbose;
      if (data.status) _state.status = { busy: data.status.busy, label: data.status.label || (data.status.busy ? 'BUSY' : 'IDLE'), workdir: data.status.workdir || '' };
      if (data.modes) _state.modes = { reasoning: data.modes.reasoning || 'off', verbosity: data.modes.verbosity || 'off' };
      break;
    case 'message':
      _state.messages = [..._state.messages, data.message];
      _state.currentToolHtml = '';
      break;
    case 'status':
      _state.status = { busy: data.status.busy, label: data.status.label || (data.status.busy ? 'BUSY' : 'IDLE'), workdir: data.status.workdir || '' };
      break;
    case 'modes':
      if (data.modes) _state.modes = { reasoning: data.modes.reasoning || 'off', verbosity: data.modes.verbosity || 'off' };
      break;
    case 'human_ask':
      if (data.message) {
        _state.humanAskState = { visible: true, message: data.message, isPassword: !!data.isPassword, resolve: null };
      }
      break;
    case 'log':
      if (_state.webVerbose) {
        _state.currentToolHtml = data.content_html || data.content || '';
      }
      break;
    case 'reasoning':
      if (messageHandlers.reasoning) messageHandlers.reasoning(data.content || '');
      break;
    case 'assistant_stream_start':
      _state.currentToolHtml = '';
      if (messageHandlers.streamStart) messageHandlers.streamStart(data.id);
      break;
    case 'assistant_stream_delta':
      if (messageHandlers.streamDelta) messageHandlers.streamDelta(data.id, data.delta);
      break;
    case 'assistant_stream_end':
    case 'assistant_stream_interrupted':
      if (messageHandlers.streamEnd) messageHandlers.streamEnd(data.id);
      break;
  }
}

export function onMessage(type, handler) {
  messageHandlers[type] = handler;
  return () => { delete messageHandlers[type]; };
}

export function sendUserInput(text, attachments) {
  console.log('[UAG] sendUserInput', {text, attCount: attachments?.length, atts: attachments?.map(a => ({type:a.type, du:!!a.data_url, name:a.name}))});
  const ws = _state.ws;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'user_input', text, attachments: attachments || [] }));
  if (text) {
    _state.inputHistory = [..._state.inputHistory, text];
  }
  _state.historyIndex = _state.inputHistory.length;
}

export function sendCommand(text) {
  const ws = _state.ws;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'command', text }));
}

export function sendInterrupt() {
  const ws = _state.ws;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'interrupt' }));
}

export function sendSetModes(reasoning, verbosity) {
  const ws = _state.ws;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'set_modes', reasoning, verbosity }));
}

export function sendHumanAskResponse(text, isPassword) {
  const ws = _state.ws;
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'human_ask_response', text, is_password: isPassword }));
  _state.humanAskState = { visible: false, message: '', isPassword: false, resolve: null };
}

export async function uploadFiles(fileList) {
  const files = Array.from(fileList);
  if (!files.length) return [];
  const fd = new FormData();
  fd.append('room', _state.roomId);
  files.forEach((f) => fd.append('files', f, f.name));
  const resp = await fetch('/upload', { method: 'POST', body: fd });
  const data = await resp.json();
  if (!data.ok) throw new Error(data.error || 'upload failed');
  return data.files || [];
}

export async function fetchGenres() {
  try {
    const resp = await fetch('/api/tool-genres');
    const data = await resp.json();
    const map = {};
    (data.genres || []).forEach((g) => { map[g.key] = g.enabled; });
    _state.genresEnabled = map;
    return map;
  } catch (_) { return {}; }
}

export async function toggleGenre(genre, enabled) {
  try {
    const resp = await fetch('/api/tool-genres', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre, enabled }),
    });
    const data = await resp.json();
    if (data.ok) {
      _state.genresEnabled = { ..._state.genresEnabled, [genre]: enabled };
    }
  } catch (_) {}
}

export async function fetchToolsEnabled() {
  try {
    const resp = await fetch('/api/tools-enabled');
    const data = await resp.json();
    return data.enabled;
  } catch (_) { return true; }
}

export async function setToolsEnabled(enabled) {
  try {
    await fetch('/api/tools-enabled', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
  } catch (_) {}
}

export async function fetchMemories() {
  try {
    const resp = await fetch('/api/memories');
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function addMemory(note) {
  try {
    const resp = await fetch('/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function updateMemory(index, note) {
  try {
    const resp = await fetch(`/api/memories/${index}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function deleteMemory(index) {
  try {
    const resp = await fetch(`/api/memories/${index}`, { method: 'DELETE' });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function fetchLogs(page = 1, perPage = 15) {
  try {
    const resp = await fetch(`/api/logs?page=${page}&per_page=${perPage}`);
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function fetchProfile() {
  try {
    const resp = await fetch('/api/profile');
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function clearProfile() {
  try {
    const resp = await fetch('/api/profile/clear', { method: 'POST' });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function profileFromLogs() {
  try {
    const resp = await fetch('/api/profile/fromlog', { method: 'POST' });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function updateProfile(profile) {
  try {
    const resp = await fetch('/api/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function postApiCommand(command, roomId) {
  try {
    const resp = await fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ room_id: roomId, command }),
    });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export { _state as state };
