import * as vscode from 'vscode';

type PendingCall = {
    resolve: (value: any) => void;
    reject: (reason: any) => void;
    timer: NodeJS.Timeout;
};

type MessageListener = (msg: any) => void;

export class WsClient {
    private ws: WebSocket | null = null;
    private pendingCalls = new Map<string, PendingCall>();
    private listeners = new Map<string, MessageListener[]>();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 10;
    private baseDelay = 1000;
    private heartbeatTimer: NodeJS.Timeout | null = null;
    private reconnectTimer: NodeJS.Timeout | null = null;
    private _isConnected = false;
    private url = '';
    private _onDidChangeStatus = new vscode.EventEmitter<boolean>();
    readonly onDidChangeStatus = this._onDidChangeStatus.event;

    get isConnected(): boolean { return this._isConnected; }

    async connect(url: string, timeoutMs = 10000): Promise<void> {
        this.url = url;
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(url);
            } catch (e) {
                reject(e);
                return;
            }
            const timer = setTimeout(() => {
                this.ws?.close();
                reject(new Error(`Connection timeout after ${timeoutMs}ms`));
            }, timeoutMs);

            this.ws.onopen = () => {
                clearTimeout(timer);
                this._isConnected = true;
                this.reconnectAttempts = 0;
                this.startHeartbeat();
                this._onDidChangeStatus.fire(true);
                resolve();
            };

            this.ws.onclose = (event) => {
                this._isConnected = false;
                this.stopHeartbeat();
                this.rejectAllPending('Connection closed');
                this._onDidChangeStatus.fire(false);
                this.scheduleReconnect();
            };

            this.ws.onerror = () => {
                clearTimeout(timer);
            };

            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data.toString());
                    this.handleMessage(msg);
                } catch (e) {
                    console.error('uag: failed to parse message', e);
                }
            };
        });
    }

    private handleMessage(msg: any) {
        // Response to a pending call
        if (msg.id && this.pendingCalls.has(msg.id)) {
            const pending = this.pendingCalls.get(msg.id)!;
            clearTimeout(pending.timer);
            this.pendingCalls.delete(msg.id);
            if (msg.ok) {
                pending.resolve(msg.result);
            } else {
                const errMsg = msg.error?.message || msg.error || 'Unknown error';
                pending.reject(new Error(errMsg));
            }
            return;
        }
        // Streaming chunk or notification
        if (msg.type) {
            const listeners = this.listeners.get(msg.type) || [];
            listeners.forEach(fn => fn(msg));
        }
    }

    async call(method: string, params: any = {}, timeoutMs = 600000): Promise<any> {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('Not connected to uag server');
        }
        const id = `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pendingCalls.delete(id);
                reject(new Error(`Timeout: ${method} (${timeoutMs}ms)`));
            }, timeoutMs);
            this.pendingCalls.set(id, { resolve, reject, timer });
            this.ws!.send(JSON.stringify({ id, method, params }));
        });
    }

    on(type: string, listener: MessageListener): void {
        if (!this.listeners.has(type)) {
            this.listeners.set(type, []);
        }
        this.listeners.get(type)!.push(listener);
    }

    off(type: string, listener: MessageListener): void {
        const list = this.listeners.get(type);
        if (list) {
            const idx = list.indexOf(listener);
            if (idx >= 0) list.splice(idx, 1);
        }
    }

    async listTools(): Promise<any[]> {
        const result = await this.call('tools/list');
        return result.tools || [];
    }

    async executeTool(name: string, args: any = {}): Promise<any> {
        const result = await this.call('tool/execute', { name, args });
        return result.result;
    }

    async readFile(path: string): Promise<{ content: string; language: string; size: number }> {
        return await this.call('files/read', { path });
    }

    async newSession(): Promise<string> {
        const result = await this.call('session/new');
        return result.id;
    }

    async listSessions(): Promise<any[]> {
        const result = await this.call('session/list');
        return result.sessions || [];
    }

    async loadSession(index: number): Promise<any> {
        return await this.call('session/load', { index });
    }

    async deleteSession(id: string): Promise<boolean> {
        const result = await this.call('session/delete', { id });
        return result.deleted;
    }

    async getConfig(key?: string): Promise<any> {
        return await this.call('config/get', key ? { key } : {});
    }

    async setConfig(key: string, value: string): Promise<void> {
        await this.call('config/set', { key, value });
    }

    async getWorkdir(): Promise<string> {
        const result = await this.call('workdir/get');
        return result.path;
    }

    async setWorkdir(path: string): Promise<void> {
        await this.call('workdir/set', { path });
    }

    async getSystemSpecs(): Promise<any> {
        return await this.call('system/specs');
    }

    private startHeartbeat() {
        this.heartbeatTimer = setInterval(async () => {
            try {
                await this.call('ping', {}, 5000);
            } catch {
                // Server may be busy processing a long request (LLM/tool call).
                // Do NOT close the connection; just try again next interval.
            }
        }, 30000);
    }

    private stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    private scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            return;
        }
        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.reconnectAttempts),
            30000
        );
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(() => {
            this.connect(this.url).catch(() => {});
        }, delay);
    }

    private rejectAllPending(reason: string) {
        for (const [id, pending] of this.pendingCalls) {
            clearTimeout(pending.timer);
            pending.reject(new Error(reason));
        }
        this.pendingCalls.clear();
    }

    async close() {
        this.reconnectAttempts = this.maxReconnectAttempts;
        this.stopHeartbeat();
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.ws?.close();
        this.ws = null;
        this._isConnected = false;
        this._onDidChangeStatus.fire(false);
    }
}
