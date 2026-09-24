const _state = $state({
  ws: null,
  connected: false,
  roomId: '',
  projectId: '',
  privateSession: false,
  authnKind: 'local',
  privateMemoryItems: [],
  messages: [],
  status: { busy: false, label: 'IDLE', workdir: '' },
  modes: { reasoning: 'off', verbosity: 'off', displayReasoning: true },
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
export function getProjectId() { return _state.projectId; }
export function getPrivateSession() { return _state.privateSession; }
export function getAuthnKind() { return _state.authnKind; }
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
    const pathRoom = (url.pathname.match(/^\/room\/([^/]+)/) || [])[1];
    const queryRoom = url.searchParams.get('room');
    return pathRoom || queryRoom || '';
  } catch (_) { return ''; }
}

let privateRoomRequest = null;

function appendConnectionError(message) {
  _state.messages = [
    ..._state.messages,
    { role: 'assistant', content: message },
  ];
}

function openRoomSocket(roomId) {
  _state.roomId = roomId;
  history.replaceState(null, '', `/room/${encodeURIComponent(roomId)}`);
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const lang = document.documentElement.lang || 'en';
  const qs = `?room=${encodeURIComponent(roomId)}&lang=${encodeURIComponent(lang)}`;
  const newWs = new WebSocket(`${protocol}//${window.location.host}/ws${qs}`);

  newWs.onopen = () => {
    _state.connected = true;
    _state.ws = newWs;
  };

  newWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleWsMessage(data);
  };

  newWs.onclose = (event) => {
    _state.connected = false;
    _state.ws = null;
    if (event.code === 1008) {
      appendConnectionError('This room is not available to the signed-in identity.');
      return;
    }
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => connect(), 2000);
  };

  newWs.onerror = () => newWs.close();
}

async function chooseProjectContext() {
  const projectsResponse = await fetch('/api/me/projects');
  const projectData = await projectsResponse.json().catch(() => ({}));
  if (!projectsResponse.ok || projectData.ok !== true) {
    throw new Error(projectData.error || 'Could not load your accessible projects.');
  }
  const projects = projectData.projects || [];
  if (!projects.length) {
    throw new Error('No project access is configured for this account.');
  }
  let projectId = projectData.bound_project || '';
  if (!projectId && projects.length === 1) projectId = projects[0];
  if (!projectId) {
    projectId = window.prompt(
      `Select a project for this private session (${projects.join(', ')}):`,
      projects[0],
    ) || '';
  }
  if (!projectId || !projects.includes(projectId)) {
    throw new Error('A listed project must be selected to start a private session.');
  }
  // The private-room API validates this selection against server-side
  // membership and binds it to the opaque room; never treat the browser value
  // itself as authorization or mutate a process-wide project context.
  return projectId;
}

async function createPrivateRoom(projectId = '') {
  const postPrivateRoom = () => fetch('/api/me/private-room', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(projectId ? { project_id: projectId } : {}),
  });
  let response = await postPrivateRoom();
  let data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    try {
      const statusResponse = await fetch('/api/auth/status');
      const status = await statusResponse.json();
      if (status.mode === 'oidc' && status.configured) {
        window.location.assign('/auth/oidc/login');
        return;
      }
    } catch (_) {}
  }
  if (response.status === 403 && (data.error === 'server project binding is required' || data.error === 'project access is not permitted')) {
    projectId = await chooseProjectContext();
    response = await postPrivateRoom();
    data = await response.json().catch(() => ({}));
  }
  if (!response.ok || data.ok !== true || !data.room_id) {
    throw new Error(data.error || `Could not create a private room (${response.status}).`);
  }
  openRoomSocket(data.room_id);
}

export function connect() {
  const ws = _state.ws;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  const room = getRoomIdFromUrl();
  if (room) {
    openRoomSocket(room);
    return;
  }
  if (privateRoomRequest) return;
  privateRoomRequest = createPrivateRoom()
    .catch((error) => {
      appendConnectionError(`Unable to start a private session: ${error.message || error}`);
    })
    .finally(() => { privateRoomRequest = null; });
}

function handleWsMessage(data) {
  switch (data.type) {
    case 'init':
      _state.privateSession = !!data.private_session;
      _state.projectId = data.project_id || '';
      _state.authnKind = data.authn_kind || 'local';
      if (!_state.privateSession) _state.privateMemoryItems = [];
      _state.messages = data.messages || [];
      _state.inputHistory = data.input_history || [];
      _state.historyIndex = _state.inputHistory.length;
      _state.webVerbose = !!data.web_verbose;
      if (data.status) _state.status = { busy: data.status.busy, label: data.status.label || (data.status.busy ? 'BUSY' : 'IDLE'), workdir: data.status.workdir || '' };
      if (data.modes) _state.modes = {
        reasoning: data.modes.reasoning || 'off',
        verbosity: data.modes.verbosity || 'off',
        displayReasoning: data.modes.display_reasoning !== undefined ? !!data.modes.display_reasoning : true,
      };
      break;
    case 'message':
      _state.messages = [..._state.messages, data.message];
      _state.currentToolHtml = '';
      break;
    case 'status':
      _state.status = { busy: data.status.busy, label: data.status.label || (data.status.busy ? 'BUSY' : 'IDLE'), workdir: data.status.workdir || '' };
      break;
    case 'modes':
      if (data.modes) _state.modes = {
        reasoning: data.modes.reasoning || 'off',
        verbosity: data.modes.verbosity || 'off',
        displayReasoning: data.modes.display_reasoning !== undefined ? !!data.modes.display_reasoning : true,
      };
      break;
    case 'human_ask':
      // Always open modal on human_ask (message may be empty in edge cases).
      _state.humanAskState = {
        visible: true,
        message: data.message || data.text || '',
        isPassword: !!(data.isPassword ?? data.is_password),
        resolve: null,
      };
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
    case 'image_event':
      if (messageHandlers.imageEvent) messageHandlers.imageEvent(data);
      break;
  }
}

export function onMessage(type, handler) {
  messageHandlers[type] = handler;
  return () => { delete messageHandlers[type]; };
}

export function sendUserInput(text, attachments) {
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

export function sendDisplayReasoningToggle() {
  sendCommand(':r');
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
  files.forEach((f) => { fd.append('files', f, f.name); });
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

function privateMemoryContext() {
  return {
    project_id: _state.projectId,
    ...(_state.privateSession ? { room_id: _state.roomId } : {}),
  };
}

function usesPrincipalMemoryApi() {
  return _state.privateSession || _state.authnKind !== 'local';
}

function privateMemoryQuery() {
  const params = new URLSearchParams(privateMemoryContext());
  return params.toString();
}

export async function fetchMemories() {
  try {
    const url = usesPrincipalMemoryApi()
      ? `/api/me/memories?${privateMemoryQuery()}`
      : '/api/memories';
    const resp = await fetch(url);
    const data = await resp.json();
    if (usesPrincipalMemoryApi() && data.ok) {
      _state.privateMemoryItems = data.memories || [];
      data.memories = _state.privateMemoryItems.map((item) => ({
        ...item,
        idx: item.memory_id,
        datetime: item.datetime || (item.ts ? new Date(item.ts * 1000).toLocaleString() : ''),
      }));
    }
    return data;
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function addMemory(note) {
  try {
    const privateSession = usesPrincipalMemoryApi();
    const resp = await fetch(privateSession ? '/api/me/memories' : '/api/memories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(privateSession
        ? { ...privateMemoryContext(), note }
        : { note }),
    });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function updateMemory(index, note) {
  try {
    if (usesPrincipalMemoryApi()) {
      const memory = _state.privateMemoryItems.find((item) => item.memory_id === index);
      if (!memory) return { ok: false, error: 'Memory is no longer available.' };
      const resp = await fetch(`/api/me/memories/${encodeURIComponent(memory.memory_id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...privateMemoryContext(),
          note,
          expected_revision: memory.revision,
        }),
      });
      return await resp.json();
    }
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
    if (usesPrincipalMemoryApi()) {
      const memory = _state.privateMemoryItems.find((item) => item.memory_id === index);
      if (!memory) return { ok: false, error: 'Memory is no longer available.' };
      const resp = await fetch(`/api/me/memories/${encodeURIComponent(memory.memory_id)}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...privateMemoryContext(),
          expected_revision: memory.revision,
        }),
      });
      return await resp.json();
    }
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
    const resp = await fetch(usesPrincipalMemoryApi() ? '/api/me/profile' : '/api/profile');
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function clearProfile() {
  try {
    if (usesPrincipalMemoryApi()) {
      return await updateProfile({ environment: {}, preferences: [], constraints: [] });
    }
    const resp = await fetch('/api/profile/clear', { method: 'POST' });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function profileFromLogs() {
  try {
    if (usesPrincipalMemoryApi()) {
      return { ok: false, error: 'Profile rebuilding from session history is disabled for authenticated users.' };
    }
    const resp = await fetch('/api/profile/fromlog', { method: 'POST' });
    return await resp.json();
  } catch (_) { return { ok: false, error: String(_) }; }
}

export async function updateProfile(profile) {
  try {
    const resp = await fetch(usesPrincipalMemoryApi() ? '/api/me/profile' : '/api/profile', {
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
