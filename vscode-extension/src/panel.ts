import * as vscode from 'vscode';
import { WsClient } from './wsClient';

export class ChatPanel {
    public static currentPanel: ChatPanel | undefined;
    private panel: vscode.WebviewPanel;
    private ws: WsClient;
    private disposables: vscode.Disposable[] = [];

    static createOrShow(context: vscode.ExtensionContext, ws: WsClient): ChatPanel {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel.panel.reveal(column);
            return ChatPanel.currentPanel;
        }

        const panel = vscode.window.createWebviewPanel(
            'uag.chat',
            'uag Chat',
            column || vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(context.extensionUri, 'media')
                ]
            }
        );

        ChatPanel.currentPanel = new ChatPanel(panel, ws);
        return ChatPanel.currentPanel;
    }

    private constructor(panel: vscode.WebviewPanel, ws: WsClient) {
        this.panel = panel;
        this.ws = ws;
        this.updateHtml();

        // Handle messages from Webview
        this.panel.webview.onDidReceiveMessage(
            async (msg: any) => {
                switch (msg.type) {
                    case 'chat':
                        await this.handleChatMessage(msg.text);
                        break;
                    case 'openFile':
                        this.openFile(msg.path, msg.line);
                        break;
                    case 'applyDiff':
                        await this.applyDiff(msg.filePath, msg.content);
                        break;
                    case 'newSession':
                        await this.handleNewSession();
                        break;
                }
            },
            null,
            this.disposables
        );

        // Listen for streaming chunks from WebSocket server
        this.ws.on('chunk', (msg: any) => {
            this.postMessage({
                type: 'chunk',
                data: msg.data || ''
            });
        });

        // Listen for progress updates from WebSocket server
        this.ws.on('progress', (msg: any) => {
            this.postMessage({
                type: 'progress',
                data: msg.data || ''
            });
        });

        // Cleanup
        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

        // Theme change listener
        vscode.window.onDidChangeActiveColorTheme((theme) => {
            this.postMessage({
                type: 'themeChanged',
                theme: theme.kind === vscode.ColorThemeKind.Dark ? 'dark'
                    : theme.kind === vscode.ColorThemeKind.HighContrast ? 'high-contrast'
                    : 'light'
            });
        });
    }

    postMessage(msg: any) {
        this.panel.webview.postMessage(msg);
    }

    /** Send a chat message from outside (e.g. editor commands) */
    async sendChatMessage(text: string): Promise<void> {
        // Tell webview to show the user message and create a streaming container
        this.postMessage({
            type: 'chat',
            text: text
        });
        // Forward to LLM
        await this.handleChatMessage(text);
    }

    private async handleChatMessage(text: string) {
        try {
            // Wait for the chat response. Streaming chunks are received
            // separately via the 'chunk' event listener during processing.
            await this.ws.call('chat', { message: text }, 300000);
            this.postMessage({ type: 'done' });
        } catch (e: any) {
            this.postMessage({ type: 'error', data: e.message });
        }
    }

    private async handleNewSession() {
        try {
            const id = await this.ws.newSession();
            this.postMessage({ type: 'system', data: `New session created: ${id}` });
        } catch (e: any) {
            this.postMessage({ type: 'error', data: e.message });
        }
    }

    private openFile(path: string, line?: number) {
        const uri = vscode.Uri.file(path);
        const options: vscode.TextDocumentShowOptions = {};
        if (line) {
            options.selection = new vscode.Range(
                new vscode.Position(line - 1, 0),
                new vscode.Position(line - 1, 0)
            );
        }
        vscode.commands.executeCommand('vscode.open', uri, options);
    }

    private async applyDiff(filePath: string, content: string) {
        const uri = vscode.Uri.file(filePath);
        try {
            const edit = new vscode.WorkspaceEdit();
            const doc = await vscode.workspace.openTextDocument(uri);
            const fullRange = new vscode.Range(
                doc.positionAt(0),
                doc.positionAt(doc.getText().length)
            );
            edit.replace(uri, fullRange, content);
            await vscode.workspace.applyEdit(edit);
            this.postMessage({ type: 'system', data: `Applied changes to ${filePath}` });
        } catch (e: any) {
            this.postMessage({ type: 'error', data: `Failed to apply: ${e.message}` });
        }
    }

    private updateHtml() {
        this.panel.webview.html = this.getHtml();
    }

    private getHtml(): string {
        return `<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            --bg: var(--vscode-editor-background, #1e1e1e);
            --bg-secondary: var(--vscode-sideBar-background, #252526);
            --text: var(--vscode-editor-foreground, #d4d4d4);
            --text-secondary: var(--vscode-descriptionForeground, #9d9d9d);
            --border: var(--vscode-panel-border, #3c3c3c);
            --accent: var(--vscode-textLink-foreground, #3794ff);
            --danger: var(--vscode-errorForeground, #f48771);
            --font-mono: var(--vscode-editor-font-family, 'Consolas', monospace);
            --font-size: var(--vscode-editor-font-size, 14px);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: var(--font-mono);
            font-size: var(--font-size);
            background: var(--bg);
            color: var(--text);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }
        #messages > div {
            padding: 8px 12px;
            margin: 4px 0;
            border-radius: 4px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .msg-user {
            background: var(--bg-secondary);
            border-left: 3px solid var(--accent);
        }
        .msg-assistant {
            border-left: 3px solid #4ec9b0;
        }
        .msg-error {
            border-left: 3px solid var(--danger);
            color: var(--danger);
        }
        .msg-system {
            font-size: 0.85em;
            color: var(--text-secondary);
            text-align: center;
        }
        #input-area {
            border-top: 1px solid var(--border);
            padding: 8px;
            background: var(--bg);
        }
        #toolbar {
            display: flex;
            gap: 4px;
            margin-bottom: 4px;
        }
        #toolbar button {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            cursor: pointer;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
        }
        #toolbar button:hover { background: var(--border); }
        #input-row {
            display: flex;
            gap: 4px;
        }
        #input {
            flex: 1;
            background: var(--bg-secondary);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 8px;
            font-family: var(--font-mono);
            font-size: var(--font-size);
            resize: none;
        }
        #input:focus { outline: none; border-color: var(--accent); }
        #btn-send {
            padding: 4px 16px;
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        #btn-send:disabled { opacity: 0.5; cursor: default; }
        #status {
            margin-top: 4px;
            font-size: 0.8em;
            color: var(--text-secondary);
        }
        .cursor-blink { animation: blink 1s step-end infinite; }
        @keyframes blink { 50% { opacity: 0; } }
        /* Markdown: code blocks */
        .msg-assistant pre, .msg-user pre {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 8px;
            overflow-x: auto;
            margin: 6px 0;
        }
        .msg-assistant code, .msg-user code {
            font-family: var(--font-mono);
            font-size: 0.9em;
        }
        .msg-assistant pre code, .msg-user pre code {
            background: none;
            border: none;
            padding: 0;
        }
        .msg-assistant :not(pre) > code, .msg-user :not(pre) > code {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 1px 4px;
        }
        .msg-assistant a, .msg-user a {
            color: var(--accent);
            text-decoration: underline;
        }
        .msg-assistant h1, .msg-user h1,
        .msg-assistant h2, .msg-user h2,
        .msg-assistant h3, .msg-user h3 {
            margin: 8px 0 4px 0;
        }
        .msg-assistant p, .msg-user p {
            margin: 4px 0;
        }
        .msg-assistant ul, .msg-user ul,
        .msg-assistant ol, .msg-user ol {
            padding-left: 20px;
            margin: 4px 0;
        }
        .msg-assistant li, .msg-user li {
            margin: 2px 0;
        }
        .msg-assistant blockquote, .msg-user blockquote {
            border-left: 3px solid var(--border);
            padding-left: 8px;
            margin: 4px 0;
            color: var(--text-secondary);
        }
        .msg-assistant table, .msg-user table {
            border-collapse: collapse;
            margin: 6px 0;
        }
        .msg-assistant th, .msg-user th,
        .msg-assistant td, .msg-user td {
            border: 1px solid var(--border);
            padding: 4px 8px;
        }
        .msg-assistant th, .msg-user th {
            background: var(--bg-secondary);
        }
    </style>
</head>
<body>
    <div id="messages"></div>
    <div id="input-area">
        <div id="toolbar">
            <button id="btn-new-session" title="New session">+ New Session</button>
        </div>
        <div id="input-row">
            <textarea id="input" placeholder="Ask anything..." rows="2"></textarea>
            <button id="btn-send" disabled>Send</button>
        </div>
        <div id="status">Connecting...</div>
    </div>
    <script>
        (function() {
            const vscode = acquireVsCodeApi();
            const messages = document.getElementById('messages');
            const input = document.getElementById('input');
            const sendBtn = document.getElementById('btn-send');
            const status = document.getElementById('status');

            function escapeHtml(s) {
                const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
                return s.replace(/[&<>"']/g, function(m) { return map[m]; });
            }

            function renderMarkdown(text) {
                let html = escapeHtml(text);
                // fenced code blocks ```lang ... ```
                html = html.replace(/```(\w*)
([\s\S]*?)```/g, function(_, lang, code) {
                    return '<pre><code' + (lang ? ' class="lang-' + lang + '"' : '') + '>'
                        + escapeHtml(code.trim()) + '</code></pre>';
                });
                // inline code `...`
                html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
                // bold **...**
                html = html.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
                // italic *...*
                html = html.replace(/\*([^*]+)\*/g, '<i>$1</i>');
                // links [text](url)
                html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
                // headings ###... to #...
                html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
                html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
                html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
                // blockquote >
                html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
                // horizontal rule ---
                html = html.replace(/^---+$/gm, '<hr>');
                // double newline = paragraph break
                html = html.replace(/

/g, '</p><p>');
                html = '<p>' + html + '</p>';
                return html;
            }

            function addMessage(text, className) {
                const div = document.createElement('div');
                div.className = className || 'msg-assistant';
                if (className === 'streaming') {
                    div.id = 'streaming';
                    div.innerHTML = '';
                } else if (className === 'msg-user' || className === 'msg-assistant') {
                    div.innerHTML = renderMarkdown(text);
                } else {
                    div.textContent = text;
                }
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
                return div;
            }

            input.addEventListener('input', () => {
                sendBtn.disabled = !input.value.trim();
                input.style.height = 'auto';
                input.style.height = Math.min(input.scrollHeight, 200) + 'px';
            });

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    send();
                }
            });

            sendBtn.addEventListener('click', send);
            document.getElementById('btn-new-session').addEventListener('click', () => {
                vscode.postMessage({ type: 'newSession' });
            });

            function send() {
                const text = input.value.trim();
                if (!text) return;
                input.value = '';
                sendBtn.disabled = true;
                input.style.height = 'auto';
                addMessage(text, 'msg-user');
                addMessage('', 'streaming');
                vscode.postMessage({ type: 'chat', text });
            }

            window.addEventListener('message', event => {
                const msg = event.data;
                switch (msg.type) {
                    case 'chat':
                        // Programmatic message (Explain Selection, etc.)
                        addMessage(msg.text, 'msg-user');
                        addMessage('', 'streaming');
                        break;
                    case 'chunk': {
                        const el = document.getElementById('streaming');
                        if (el) el.textContent += msg.data;
                        break;
                    }
                    case 'progress':
                        status.textContent = msg.data;
                        break;
                    case 'done': {
                        const el = document.getElementById('streaming');
                        if (el) {
                            const raw = el.textContent || '';
                            el.innerHTML = renderMarkdown(raw);
                            el.id = '';
                        }
                        sendBtn.disabled = false;
                        // Re-enable send button based on input
                        if (input.value.trim()) sendBtn.disabled = false;
                        status.textContent = 'Ready';
                        break;
                    }
                    case 'error':
                        addMessage(msg.data, 'msg-error');
                        sendBtn.disabled = false;
                        if (input.value.trim()) sendBtn.disabled = false;
                        break;
                    case 'system':
                        addMessage(msg.data, 'msg-system');
                        break;
                    case 'themeChanged':
                        document.body.className = 'theme-' + msg.theme;
                        break;
                }
                messages.scrollTop = messages.scrollHeight;
            });

            status.textContent = 'Ready';
            input.focus();
        })();
    </script>
</body>
</html>`;
    }

    private dispose() {
        ChatPanel.currentPanel = undefined;
        this.panel.dispose();
        this.disposables.forEach(d => d.dispose());
    }
}
