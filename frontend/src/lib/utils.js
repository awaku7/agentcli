export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export function basename(path) {
  return String(path || '').split(/[\\/]/).filter(Boolean).pop() || '';
}

export function isImageAttachment(att) {
  const type = String((att && (att.type || att.mime)) || '').toLowerCase();
  const path = String((att && (att.saved_path || att.path || att.file_path || att.name)) || '').toLowerCase();
  return type.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(path);
}

export function isAudioAttachment(att) {
  const type = String((att && (att.type || att.mime)) || '').toLowerCase();
  const path = String((att && (att.saved_path || att.path || att.file_path || att.name)) || '').toLowerCase();
  return type.startsWith('audio/') || /\.(mp3|wav|m4a|aac|flac|ogg|opus)$/i.test(path);
}

export function extractHtmlFromText(text) {
  if (!text) return '';
  const codeBlockRegex = /```(?:html|xml|xhtml)?\s*([\s\S]*?)```/gi;
  let match;
  let lastHtml = '';
  while ((match = codeBlockRegex.exec(text)) !== null) {
    const code = match[1].trim();
    if (code.includes('<html') || code.includes('<!DOCTYPE') || code.includes('<div') ||
        code.includes('<button') || code.includes('<script') || code.includes('<style')) {
      lastHtml = code;
    }
  }
  if (!lastHtml) {
    const htmlTagRegex = /<html[\s\S]*?<\/html>/gi;
    const tagMatch = htmlTagRegex.exec(text);
    if (tagMatch) lastHtml = tagMatch[0];
  }
  return lastHtml;
}

export function ansiToHtml(text) {
  if (!text) return '';
  const ansiRegex = /\x1b\[([0-9;]*)m/g;
  let match;
  let lastIndex = 0;
  let result = '';
  let openSpans = 0;
  while ((match = ansiRegex.exec(text)) !== null) {
    result += escapeHtml(text.slice(lastIndex, match.index));
    const codes = match[1].split(';');
    if (codes.indexOf('0') >= 0 || match[1] === '') {
      while (openSpans > 0) { result += '</span>'; openSpans--; }
    } else {
      const styles = [];
      codes.forEach((code) => {
        if (code === '31') styles.push('color:#ef4444');
        else if (code === '32') styles.push('color:#10b981');
        else if (code === '33') styles.push('color:#f59e0b');
        else if (code === '34') styles.push('color:#3b82f6');
        else if (code === '35') styles.push('color:#8b5cf6');
        else if (code === '36') styles.push('color:#06b6d4');
        else if (code === '1') styles.push('font-weight:bold');
        else if (code === '3') styles.push('font-style:italic');
        else if (code === '4') styles.push('text-decoration:underline');
      });
      if (styles.length > 0) { result += `<span style="${styles.join(';')}">`; openSpans++; }
    }
    lastIndex = ansiRegex.lastIndex;
  }
  result += escapeHtml(text.slice(lastIndex));
  while (openSpans > 0) { result += '</span>'; openSpans--; }
  return result;
}

export function linkifyHtml(escapedHtml) {
  const urlRe = /\b(https?:\/\/[^\s<>"']+|www\.[^\s<>"']+)/gi;
  return escapedHtml.replace(urlRe, (m) => {
    const href = m.indexOf('www.') === 0 ? 'https://' + m : m;
    return `<a href="${href}" target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 underline break-all">${m}</a>`;
  });
}

export function formatMessageBody(body) {
  if (!body) return '';
  if (body.indexOf('```') < 0) return linkifyHtml(ansiToHtml(body));
  const parts = body.split(/(```(?:\w+)?[\s\S]*?```)/);
  let result = '';
  for (const part of parts) {
    if (part.indexOf('```') === 0 && part.slice(-3) === '```') {
      const match = part.match(/```(\w+)?\s*([\s\S]*?)```/);
      if (match) {
        const code = match[2];
        const lang = (match[1] || 'code').toUpperCase();
        result += `<details class="code-block my-2 rounded-lg overflow-hidden" style="border:1px solid var(--border-color);background:var(--bg-surface-alt);">`;
        result += `<summary class="px-3 py-1.5 text-xs font-bold cursor-pointer select-none flex justify-between items-center" style="background:var(--bg-surface);color:var(--text-secondary);">`;
        result += `<span>📄 ${lang}</span><span class="text-[10px] opacity-60">click to expand</span></summary>`;
        result += `<pre class="p-3 text-xs font-mono overflow-auto max-h-[250px] whitespace-pre" style="background:#0f172a;color:#e2e8f0;">${escapeHtml(code.trim())}</pre>`;
        result += '</details>';
      } else {
        result += linkifyHtml(ansiToHtml(part));
      }
    } else {
      result += linkifyHtml(ansiToHtml(part));
    }
  }
  return result;
}

export function normalizeToolMessage(msg) {
  const role = String(msg.role || '').toLowerCase();
  const name = String(msg.name || '').toLowerCase();
  const toolLabel = name || 'tool';
  let body = String(msg.content || '');
  if (role !== 'tool') return body;
  const trimmed = body.trim();
  if (!trimmed) return '';
  let parsed = null;
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try { parsed = JSON.parse(trimmed); } catch (_) {}
  }
  if (parsed && typeof parsed === 'object') {
    if (Array.isArray(parsed.files)) {
      return `${toolLabel}: ${parsed.files.map(f => basename(f)).filter(Boolean).join(', ')}`;
    }
    if (parsed.saved_path) return `${toolLabel}: ${basename(parsed.saved_path)}`;
    if (typeof parsed.message === 'string' && parsed.message.trim()) return `${toolLabel}: ${parsed.message.trim()}`;
    if (parsed.ok === true) return `${toolLabel}: done`;
    return `${toolLabel}: result`;
  }
  return `${toolLabel}: ${trimmed.split('\n')[0].slice(0, 200)}`;
}

export function getRoleClass(role) {
  switch (String(role).toLowerCase()) {
    case 'user': return 'role-user';
    case 'assistant': return 'role-assistant';
    case 'tool': return 'role-tool';
    case 'system': return 'hidden';
    default: return '';
  }
}
