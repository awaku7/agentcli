<script>
  import { t } from '../../lib/i18n.svelte.js';
  import { getModes, getGenresEnabled, getStatus, sendSetModes, toggleGenre, sendCommand, sendDisplayReasoningToggle, fetchToolsEnabled, setToolsEnabled, fetchMemories, addMemory, updateMemory, deleteMemory, fetchLogs, fetchProfile, clearProfile, profileFromLogs, updateProfile } from '../../lib/stores.svelte.js';

  let { onClose } = $props();
  let tab = $state('settings');

  // --- Settings tab ---
  let modes = $derived(getModes());
  let genresEnabled = $derived(getGenresEnabled());
  let genreKeys = ['basic', 'comm', 'office', 'devel', 'iot', 'exec', 'external', 'media', 'file', 'index'];
  let genres = $derived(genreKeys.map(k => ({ key: k, enabled: genresEnabled[k] || false })));
  let toolsEnabled = $state(true);

  function onReasoningChange(e) { sendSetModes(e.target.value, modes.verbosity); }
  function onVerbosityChange(e) { sendSetModes(modes.reasoning, e.target.value); }
  function onGenreToggle(genre, checked) { toggleGenre(genre, checked); }

  $effect(() => {
    fetchToolsEnabled().then(v => { if (v !== undefined) toolsEnabled = v; });
  });

  async function doToolsToggle() {
    const newVal = !toolsEnabled;
    await setToolsEnabled(newVal);
    toolsEnabled = newVal;
    sendCommand(newVal ? ':tools on' : ':tools off');
  }

  // --- Auto tab ---
  let autoGoal = $state('');
  let autoMaxRounds = $state(10);

  function doAuto() {
    if (!autoGoal.trim()) return;
    sendCommand(`:auto ${autoGoal.trim()} --max-rounds ${autoMaxRounds}`);
    autoGoal = '';
  }

  // --- Logs tab ---
  let logsData = $state(null);
  let logsLoading = $state(false);
  let logsPage = $state(1);

  async function loadLogs(page) {
    if (page !== undefined) logsPage = page;
    logsLoading = true;
    logsData = null;
    try {
      const r = await fetchLogs(logsPage, 15);
      logsData = r;
    } catch (e) {
      logsData = { error: String(e) };
    } finally {
      logsLoading = false;
    }
  }

  function goLogPage(page) {
    logsPage = page;
    loadLogs(page);
  }

  function doLoadLog(path) {
    sendCommand(`:load "${path}"`);
    onClose?.();
  }

  function formatSize(bytes) {
    if (!bytes) return '0B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + sizes[i];
  }

  function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleString();
  }

  // --- Memory tab ---
  let memories = $state([]);
  let memLoading = $state(false);
  let editingIdx = $state(-1);
  let editText = $state('');
  let newMemText = $state('');

  async function loadMemories() {
    memLoading = true;
    try {
      const r = await fetchMemories();
      if (r.ok) memories = r.memories || [];
    } catch (e) {
      memories = [];
    } finally {
      memLoading = false;
    }
  }

  function startEdit(idx, note) {
    editingIdx = idx;
    editText = note;
  }

  function cancelEdit() {
    editingIdx = -1;
    editText = '';
  }

  async function saveEdit(idx) {
    if (!editText.trim()) return;
    await updateMemory(idx, editText.trim());
    cancelEdit();
    loadMemories();
  }

  async function doDelete(idx) {
    await deleteMemory(idx);
    loadMemories();
  }

  async function doAddMemory() {
    if (!newMemText.trim()) return;
    await addMemory(newMemText.trim());
    newMemText = '';
    loadMemories();
  }

  // --- Profile tab ---
  let profileData = $state(null);
  let profileLoading = $state(false);
  let profileClearing = $state(false);
  let profileBuilding = $state(false);
  let profileEditing = $state(false);
  let profileEditEnv = $state('');
  let profileEditPrefs = $state('');
  let profileEditCons = $state('');

  async function loadProfile() {
    profileLoading = true;
    profileData = null;
    try {
      const r = await fetchProfile();
      profileData = r.ok ? r.profile : null;
    } catch (e) {
      profileData = null;
    } finally {
      profileLoading = false;
    }
  }

  function startProfileEdit() {
    if (!profileData) return;
    profileEditing = true;
    const env = profileData.environment || {};
    const _NL = String.fromCharCode(10);
    profileEditEnv = Object.entries(env).map(([k, v]) => `${k}: ${v}`).join(_NL);
    profileEditPrefs = (profileData.preferences || []).join(_NL);
    profileEditCons = (profileData.constraints || []).join(_NL);
  }

  function cancelProfileEdit() {
    profileEditing = false;
  }

  async function saveProfileEdit() {
    // Parse environment lines (key: value)
    const env = {};
    const _NL2 = String.fromCharCode(10);
    for (const line of profileEditEnv.split(_NL2)) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const colon = trimmed.indexOf(':');
      if (colon > 0) {
        env[trimmed.slice(0, colon).trim()] = trimmed.slice(colon + 1).trim();
      } else {
        env[trimmed] = '';
      }
    }
    const prefs = profileEditPrefs.split(_NL2).map(l => l.trim()).filter(Boolean);
    const cons = profileEditCons.split(_NL2).map(l => l.trim()).filter(Boolean);
    const r = await updateProfile({ environment: env, preferences: prefs, constraints: cons });
    if (r.ok) profileData = r.profile;
    profileEditing = false;
  }

  async function doClearProfile() {
    profileClearing = true;
    await clearProfile();
    profileClearing = false;
    loadProfile();
  }

  async function doProfileFromLogs() {
    profileBuilding = true;
    await profileFromLogs();
    profileBuilding = false;
    loadProfile();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 z-50 flex items-start justify-center pt-[6vh]"
  style="background:rgba(0,0,0,0.4);backdrop-filter:blur(6px);"
  onclick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
  role="dialog" tabindex="-1"
>
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions a11y_no_static_element_interactions -->
  <div
    class="rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden"
    style="background:var(--bg-surface);border:1px solid var(--border-color);animation:uag-fadeIn 0.15s ease-out;max-height:85vh;display:flex;flex-direction:column;"
  >
    <!-- Tabs -->
    <div class="flex border-b shrink-0 overflow-x-auto" style="border-color:var(--border-color);">
      <button onclick={() => tab = 'settings'} class="px-5 py-3 text-sm font-bold transition cursor-pointer whitespace-nowrap"
        style="background:{tab === 'settings' ? 'var(--accent-subtle)' : 'transparent'};color:{tab === 'settings' ? 'var(--accent)' : 'var(--text-secondary)'};border-bottom:{tab === 'settings' ? '2px solid var(--accent)' : '2px solid transparent'};"
      >⚙ {t('settings')}</button>
      <button onclick={() => tab = 'auto'} class="px-5 py-3 text-sm font-bold transition cursor-pointer whitespace-nowrap"
        style="background:{tab === 'auto' ? 'var(--accent-subtle)' : 'transparent'};color:{tab === 'auto' ? 'var(--accent)' : 'var(--text-secondary)'};border-bottom:{tab === 'auto' ? '2px solid var(--accent)' : '2px solid transparent'};"
      >🤖 Auto</button>
      <button onclick={() => { tab = 'logs'; loadLogs(); }} class="px-5 py-3 text-sm font-bold transition cursor-pointer whitespace-nowrap"
        style="background:{tab === 'logs' ? 'var(--accent-subtle)' : 'transparent'};color:{tab === 'logs' ? 'var(--accent)' : 'var(--text-secondary)'};border-bottom:{tab === 'logs' ? '2px solid var(--accent)' : '2px solid transparent'};"
      >📋 Logs</button>
      <button onclick={() => { tab = 'mem'; loadMemories(); }} class="px-5 py-3 text-sm font-bold transition cursor-pointer whitespace-nowrap"
        style="background:{tab === 'mem' ? 'var(--accent-subtle)' : 'transparent'};color:{tab === 'mem' ? 'var(--accent)' : 'var(--text-secondary)'};border-bottom:{tab === 'mem' ? '2px solid var(--accent)' : '2px solid transparent'};"
      >🧠 {t('tabMemory')}</button>
      <button onclick={() => { tab = 'profile'; loadProfile(); }} class="px-5 py-3 text-sm font-bold transition cursor-pointer whitespace-nowrap"
        style="background:{tab === 'profile' ? 'var(--accent-subtle)' : 'transparent'};color:{tab === 'profile' ? 'var(--accent)' : 'var(--text-secondary)'};border-bottom:{tab === 'profile' ? '2px solid var(--accent)' : '2px solid transparent'};"
      >📊 {t('tabProfile')}</button>
    </div>

    <!-- ⚙ Settings Tab -->
    {#if tab === 'settings'}
      <div class="p-5 space-y-4 overflow-y-auto">
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium min-w-[80px]" style="color:var(--text-secondary);">{t('reasoning')}:</span>
          <select value={modes.reasoning} onchange={onReasoningChange}
            class="flex-1 border rounded-lg px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 transition"
            style="border-color:var(--border-color);color:var(--text-primary);background:var(--bg-surface-alt);--tw-ring-color:var(--accent);"
          >
            <option value="off">off</option><option value="auto">auto</option>
            <option value="minimal">minimal</option><option value="low">low</option>
            <option value="medium">medium</option><option value="high">high</option><option value="xhigh">xhigh</option>
          </select>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium min-w-[80px]" style="color:var(--text-secondary);">{t('verbosity')}:</span>
          <select value={modes.verbosity} onchange={onVerbosityChange}
            class="flex-1 border rounded-lg px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 transition"
            style="border-color:var(--border-color);color:var(--text-primary);background:var(--bg-surface-alt);--tw-ring-color:var(--accent);"
          >
            <option value="off">off</option><option value="low">low</option>
            <option value="medium">medium</option><option value="high">high</option>
          </select>
        </div>
        <div class="flex items-center justify-between pt-2 border-t" style="border-color:var(--border-color);">
          <span class="text-sm font-medium" style="color:var(--text-secondary);">{t('displayReasoning')}</span>
          <button aria-label={t('displayReasoning')} onclick={sendDisplayReasoningToggle} class="relative w-12 h-6 rounded-full transition cursor-pointer"
            style="background:{modes.displayReasoning ? 'var(--accent)' : 'var(--border-color)'};border:1px solid {modes.displayReasoning ? 'var(--accent)' : 'var(--text-tertiary)'};"
          ><span class="absolute top-0.5 w-5 h-5 rounded-full shadow transition" style="background:{modes.displayReasoning ? '#fff' : 'var(--text-primary)'};left:{modes.displayReasoning ? 'calc(100% - 22px)' : '2px'};outline:1px solid var(--border-color);outline-offset:-1px;\"></span></button>
        </div>
        <div>
          <div class="text-sm font-medium mb-2" style="color:var(--text-secondary);">{t('tools')}:</div>
          <div class="flex flex-wrap gap-2">
            {#each genres as g}
              <label class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition hover:opacity-80"
                style="background:{g.enabled ? 'var(--accent-subtle)' : 'var(--bg-surface-alt)'};color:{g.enabled ? 'var(--accent)' : 'var(--text-secondary)'};border:1px solid {g.enabled ? 'var(--accent)' : 'var(--border-color)'};"
              >
                <input type="checkbox" checked={g.enabled} onchange={(e) => onGenreToggle(g.key, e.target.checked)} class="hidden" />
                {g.key}
              </label>
            {/each}
          </div>
        </div>
        <div class="flex items-center justify-between pt-2 border-t" style="border-color:var(--border-color);">
          <span class="text-sm font-medium" style="color:var(--text-secondary);">{t('toolSending')}</span>
          <button aria-label={t('toolSending')} onclick={doToolsToggle} class="relative w-12 h-6 rounded-full transition cursor-pointer"
            style="background:{toolsEnabled ? 'var(--accent)' : 'var(--border-color)'};border:1px solid {toolsEnabled ? 'var(--accent)' : 'var(--text-tertiary)'};"
          ><span class="absolute top-0.5 w-5 h-5 rounded-full shadow transition" style="background:{toolsEnabled ? '#fff' : 'var(--text-primary)'};left:{toolsEnabled ? 'calc(100% - 22px)' : '2px'};outline:1px solid var(--border-color);outline-offset:-1px;"></span></button>
        </div>
      </div>

    <!-- 🤖 Auto Tab -->
    {:else if tab === 'auto'}
      <div class="p-5 space-y-4 overflow-y-auto">
        <div class="text-sm font-medium" style="color:var(--text-secondary);">{t('autoGoal')}</div>
        <textarea bind:value={autoGoal} rows="3"
          class="w-full p-3 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 transition resize-none"
          style="background:var(--bg-surface-alt);color:var(--text-primary);border:1px solid var(--border-color);--tw-ring-color:var(--accent);"
          placeholder={t('autoPlaceholder')}
        ></textarea>
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium" style="color:var(--text-secondary);">{t('maxRounds')}:</span>
          <input type="range" bind:value={autoMaxRounds} min="1" max="30" class="flex-1 accent-blue-500" />
          <span class="text-sm font-mono font-bold min-w-[2em]" style="color:var(--accent);">{autoMaxRounds}</span>
        </div>
        <button onclick={doAuto} disabled={!autoGoal.trim()}
          class="w-full py-3 rounded-xl font-bold text-white shadow-sm transition hover:brightness-110 active:scale-[0.98] disabled:opacity-40"
          style="background:linear-gradient(135deg, var(--accent), #8b5cf6);"
        >▶ {t('startAuto')}</button>
      </div>

    <!-- 📋 Logs Tab -->
    {:else if tab === 'logs'}
      <div class="p-5 overflow-y-auto">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium" style="color:var(--text-secondary);">{t('sessionLogs')}</span>
          <button onclick={() => loadLogs()} disabled={logsLoading}
            class="text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer disabled:opacity-50"
            style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);"
          >⟳ {t('refresh')}</button>
        </div>
        {#if logsLoading}
          <div class="text-xs py-8 text-center" style="color:var(--text-tertiary);">{t('loading')}</div>
        {:else if logsData?.logs?.length}
          <div class="space-y-1.5">
            {#each logsData.logs as log}
              <button onclick={() => doLoadLog(log.path)}
                class="w-full text-left px-3 py-2.5 rounded-xl text-xs transition hover:scale-[1.01] active:scale-[0.99] cursor-pointer"
                style="background:var(--bg-surface-alt);color:var(--text-primary);border:1px solid var(--border-color);"
              >
                <div class="font-medium truncate">{log.name}</div>
                {#if log.summary}
                  <div class="truncate mt-0.5" style="color:var(--text-secondary);">{log.summary}</div>
                {/if}
                <div class="flex gap-3 mt-0.5" style="color:var(--text-tertiary);">
                  <span>{formatSize(log.size)}</span>
                  <span>{log.mtime ? formatTime(log.mtime) : ''}</span>
                  {#if log.has_responses_state}
                    <span title={log.latest_response_id || ''}>[R] {log.response_count ?? 0} · {(log.latest_response_id || '').slice(0, 18)}</span>
                  {/if}
                </div>
              </button>
            {/each}
          </div>
          <div class="flex items-center justify-center gap-2 mt-3 pt-3 border-t" style="border-color:var(--border-color);">
            <button onclick={() => goLogPage(logsPage - 1)} disabled={logsPage <= 1}
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer disabled:opacity-30"
              style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);"
            >{t('prevPage')}</button>
            <span class="text-xs font-mono" style="color:var(--text-tertiary);">
              {logsData.page} / {logsData.total_pages} ({logsData.total} {t('filesCount', '').replace('{page}', logsData.page).replace('{total}', logsData.total_pages).replace('{all}', logsData.total)})
            </span>
            <button onclick={() => goLogPage(logsPage + 1)} disabled={logsPage >= logsData.total_pages}
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer disabled:opacity-30"
              style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);"
            >{t('nextPage')}</button>
          </div>
        {:else if logsData?.error}
          <div class="text-xs py-4 text-center" style="color:var(--status-busy);">{t('error')}: {logsData.error}</div>
        {:else}
          <div class="text-xs py-8 text-center" style="color:var(--text-tertiary);">{t('noLogsFound')}</div>
        {/if}
      </div>

    <!-- 🧠 Memory Tab -->
    {:else if tab === 'mem'}
      <div class="p-5 overflow-y-auto">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium" style="color:var(--text-secondary);">{t('longTermMemory')}</span>
          <button onclick={loadMemories} disabled={memLoading}
            class="text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer disabled:opacity-50"
            style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);"
          >⟳ {t('refresh')}</button>
        </div>
        <div class="flex gap-2 mb-4">
          <input bind:value={newMemText} onkeydown={(e) => { if (e.key === 'Enter') doAddMemory(); }}
            class="flex-1 px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 transition"
            style="background:var(--bg-surface-alt);color:var(--text-primary);border:1px solid var(--border-color);--tw-ring-color:var(--accent);"
            placeholder={t('addNewMemory')}
          />
          <button onclick={doAddMemory} disabled={!newMemText.trim()}
            class="px-4 py-2 rounded-lg text-xs font-bold text-white transition hover:brightness-110 active:scale-[0.97] disabled:opacity-40"
            style="background:linear-gradient(135deg, var(--accent), #8b5cf6);"
          >{t('add')}</button>
        </div>
        {#if memLoading}
          <div class="text-xs py-8 text-center" style="color:var(--text-tertiary);">{t('loading')}</div>
        {:else if memories.length}
          <div class="space-y-2">
            {#each memories as mem}
              <div class="p-3 rounded-xl" style="background:var(--bg-surface-alt);border:1px solid var(--border-color);">
                {#if editingIdx === mem.idx}
                  <textarea bind:value={editText} rows="2"
                    class="w-full p-2 rounded-lg text-xs font-medium focus:outline-none focus:ring-2 transition resize-none mb-2"
                    style="background:var(--bg-surface);color:var(--text-primary);border:1px solid var(--accent);--tw-ring-color:var(--accent);"
                  ></textarea>
                  <div class="flex gap-2 justify-end">
                    <button onclick={cancelEdit} class="text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer"
                      style="background:var(--bg-surface);color:var(--text-secondary);border:1px solid var(--border-color);">{t('cancel')}</button>
                    <button onclick={() => saveEdit(mem.idx)} disabled={!editText.trim()}
                      class="text-xs px-3 py-1.5 rounded-lg font-bold text-white transition hover:brightness-110 disabled:opacity-40"
                      style="background:linear-gradient(135deg, var(--accent), #8b5cf6);">{t('save')}</button>
                  </div>
                {:else}
                  <div class="flex justify-between gap-2">
                    <div class="flex-1 min-w-0">
                      <div class="text-xs font-mono truncate" style="color:var(--text-tertiary);">{mem.datetime || ''}</div>
                      <div class="text-sm mt-1 break-words">{mem.note}</div>
                    </div>
                    <div class="flex gap-1 shrink-0">
                      <button onclick={() => startEdit(mem.idx, mem.note)} class="px-2 py-1 rounded text-xs font-medium transition cursor-pointer hover:opacity-80"
                        style="color:var(--accent);" title={t('edit')}>✏️</button>
                      <button onclick={() => doDelete(mem.idx)} class="px-2 py-1 rounded text-xs font-medium transition cursor-pointer hover:opacity-80"
                        style="color:#ef4444;" title={t('delete')}>🗑️</button>
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <div class="text-xs py-8 text-center" style="color:var(--text-tertiary);">{t('noMemoryEntries')}</div>
        {/if}
      </div>

    <!-- 📊 Profile Tab -->
    {:else if tab === 'profile'}
      <div class="p-5 overflow-y-auto">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium" style="color:var(--text-secondary);">{t('userProfile')}</span>
          <div class="flex gap-2">
            {#if profileEditing}
              <button onclick={saveProfileEdit} class="text-xs px-3 py-1.5 rounded-lg font-bold text-white transition hover:brightness-110"
                style="background:linear-gradient(135deg, var(--accent), #8b5cf6);">{t('save')}</button>
              <button onclick={cancelProfileEdit} class="text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer"
                style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);">{t('cancel')}</button>
            {:else}
              <button onclick={startProfileEdit} disabled={!profileData}
                class="text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer disabled:opacity-50"
                style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);">✏️ {t('edit')}</button>
              <button onclick={doProfileFromLogs} disabled={profileBuilding}
                class="text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer disabled:opacity-50"
                style="background:var(--bg-surface-alt);color:var(--text-secondary);border:1px solid var(--border-color);"
              >{profileBuilding ? t('building') : t('rebuildFromLogs')}</button>
              <button onclick={doClearProfile} disabled={profileClearing}
                class="text-xs px-3 py-1.5 rounded-lg font-medium transition cursor-pointer disabled:opacity-50"
                style="background:rgba(239,68,68,0.1);color:var(--status-busy);border:1px solid rgba(239,68,68,0.3);"
              >{profileClearing ? t('clearing') : t('clear')}</button>
            {/if}
          </div>
        </div>
        {#if profileLoading}
          <div class="text-xs py-8 text-center" style="color:var(--text-tertiary);">{t('loading')}</div>
        {:else if profileEditing}
          <div class="space-y-3">
            <div>
              <div class="text-xs font-medium mb-1" style="color:var(--text-tertiary);">{t('envEditHint')}</div>
              <textarea bind:value={profileEditEnv} rows="4" class="w-full p-2.5 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 transition resize-none"
                style="background:var(--bg-surface-alt);color:var(--text-primary);border:1px solid var(--border-color);--tw-ring-color:var(--accent);"
              ></textarea>
            </div>
            <div>
              <div class="text-xs font-medium mb-1" style="color:var(--text-tertiary);">{t('prefsEditHint')}</div>
              <textarea bind:value={profileEditPrefs} rows="3" class="w-full p-2.5 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 transition resize-none"
                style="background:var(--bg-surface-alt);color:var(--text-primary);border:1px solid var(--border-color);--tw-ring-color:var(--accent);"
              ></textarea>
            </div>
            <div>
              <div class="text-xs font-medium mb-1" style="color:var(--text-tertiary);">{t('consEditHint')}</div>
              <textarea bind:value={profileEditCons} rows="3" class="w-full p-2.5 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 transition resize-none"
                style="background:var(--bg-surface-alt);color:var(--text-primary);border:1px solid var(--border-color);--tw-ring-color:var(--accent);"
              ></textarea>
            </div>
          </div>
        {:else if profileData}
          {#if profileData.environment && Object.keys(profileData.environment).length}
            <div class="mb-4">
              <div class="text-xs font-medium mb-1.5" style="color:var(--text-tertiary);">{t('environment')}</div>
              <div class="space-y-1">
                {#each Object.entries(profileData.environment) as [key, val]}
                  <div class="flex gap-2 text-xs px-3 py-1.5 rounded-lg" style="background:var(--bg-surface-alt);">
                    <span class="font-medium min-w-[100px]" style="color:var(--text-secondary);">{key}</span>
                    <span style="color:var(--text-primary);">{typeof val === 'string' ? val : JSON.stringify(val)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
          {#if profileData.preferences?.length}
            <div class="mb-4">
              <div class="text-xs font-medium mb-1.5" style="color:var(--text-tertiary);">{t('preferences')}</div>
              <div class="space-y-1">
                {#each profileData.preferences as pref}
                  <div class="text-xs px-3 py-1.5 rounded-lg" style="background:var(--bg-surface-alt);color:var(--text-primary);">{pref}</div>
                {/each}
              </div>
            </div>
          {/if}
          {#if profileData.constraints?.length}
            <div>
              <div class="text-xs font-medium mb-1.5" style="color:var(--text-tertiary);">{t('constraints')}</div>
              <div class="space-y-1">
                {#each profileData.constraints as constraint}
                  <div class="text-xs px-3 py-1.5 rounded-lg" style="background:var(--bg-surface-alt);color:var(--text-primary);">{constraint}</div>
                {/each}
              </div>
            </div>
          {/if}
          {#if (!profileData.environment || !Object.keys(profileData.environment).length) && !profileData.preferences?.length && !profileData.constraints?.length}
            <div class="text-xs py-8 text-center" style="color:var(--text-tertiary);">{t('profileEmpty')}</div>
          {/if}
        {:else}
          <div class="text-xs py-8 text-center" style="color:var(--text-tertiary);">{t('noProfileData')}</div>
        {/if}
      </div>
    {/if}
  </div>
</div>
