import * as vscode from 'vscode';
import * as cp from 'child_process';
import { WsClient } from './wsClient';
import { ChatPanel } from './panel';
import { ToolTreeProvider } from './treeProvider';
import { EditorIntegration } from './editorIntegration';

let wsClient: WsClient;
let outputChannel: vscode.OutputChannel;
let serverProcess: cp.ChildProcess | null = null;
let statusBarItem: vscode.StatusBarItem;
let editorIntegration: EditorIntegration;

export async function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel('uag');
    log('INFO', 'uag extension activating...');

    // Store context for EditorIntegration
    (global as any).__uag_extension_context = context;

    // Status bar
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right, 100
    );
    statusBarItem.text = '$(hubot) uag: starting...';
    statusBarItem.command = 'uag.chat';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Check Python availability
    const pythonPath = vscode.workspace.getConfiguration('uag')
        .get<string>('pythonPath', 'python');
    const pythonOk = await checkPython(pythonPath);
    if (!pythonOk) {
        statusBarItem.text = '$(warning) uag: Python not found';
        const action = await vscode.window.showErrorMessage(
            'uag: Python not found. Install Python and run: pip install uag',
            'Install Guide', 'Retry'
        );
        if (action === 'Install Guide') {
            vscode.env.openExternal(
                vscode.Uri.parse('https://pypi.org/project/uag/')
            );
        }
        return;
    }

    // Check uag installation
    const uagOk = await checkUagInstalled(pythonPath);
    if (!uagOk) {
        statusBarItem.text = '$(warning) uag: not installed';
        const action = await vscode.window.showErrorMessage(
            'uag: Package not found. Run: pip install uag',
            'Install Now', 'Retry'
        );
        if (action === 'Install Now') {
            await runInTerminal(`"${pythonPath}" -m pip install uag`);
        }
        return;
    }

    // Start WebSocket server and wait for it to be ready
    const port = vscode.workspace.getConfiguration('uag')
        .get<number>('port', 18765);
    statusBarItem.text = '$(hubot) uag: starting server...';
    try {
        serverProcess = await startServer(pythonPath, port);
    } catch (e: any) {
        statusBarItem.text = '$(error) uag: server failed';
        vscode.window.showErrorMessage(
            `uag: Failed to start server: ${e.message}`
        );
        return;
    }

    // Connect WebSocket client
    wsClient = new WsClient();

    // Update status on connection change
    wsClient.onDidChangeStatus((connected) => {
        statusBarItem.text = connected
            ? '$(hubot) uag: connected'
            : '$(warning) uag: disconnected';
    });

    try {
        await wsClient.connect(`ws://127.0.0.1:${port}`, 15000);
    } catch (e: any) {
        statusBarItem.text = '$(error) uag: connection failed';
        vscode.window.showErrorMessage(
            `uag: Failed to connect to server: ${e.message}`
        );
        return;
    }

    // Set workdir to workspace root after connection is established
    const folders = vscode.workspace.workspaceFolders;
    if (folders && folders.length > 0) {
        try {
            await wsClient.setWorkdir(folders[0].uri.fsPath);
        } catch (e: any) {
            log('WARN', `Failed to set workdir: ${e.message}`);
        }
    }

    // Listen for workspace folder changes (Open Folder / Switch Folder)
    context.subscriptions.push(
        vscode.workspace.onDidChangeWorkspaceFolders(async (event) => {
            const removed = event.removed;
            if (removed.length > 0) {
                log('INFO', `Workspace folder removed: ${removed.map(f => f.uri.fsPath).join(', ')}`);
            }
            const target = vscode.workspace.workspaceFolders?.[0] || event.added[0];
            if (target) {
                const newPath = target.uri.fsPath;
                log('INFO', `Workspace folder changed. Setting workdir to: ${newPath}`);
                try {
                    await wsClient.setWorkdir(newPath);
                    log('INFO', `Workdir updated to: ${newPath}`);
                } catch (e: any) {
                    log('WARN', `Failed to update workdir: ${e.message}`);
                }
            } else {
                log('WARN', 'Workspace folder changed but no folder available');
            }
        })
    );

    // Editor integration
    editorIntegration = new EditorIntegration(wsClient);

    // Tool tree view
    const treeProvider = new ToolTreeProvider(wsClient);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('uag.chat', () => {
            ChatPanel.createOrShow(context, wsClient);
        }),
        vscode.commands.registerCommand('uag.explain', async () => {
            await editorIntegration.explainSelection();
        }),
        vscode.commands.registerCommand('uag.refactor', async () => {
            await editorIntegration.refactorSelection();
        }),
        vscode.commands.registerCommand('uag.fix', async () => {
            await editorIntegration.fixError();
        }),
        vscode.commands.registerCommand('uag.newSession', async () => {
            try {
                await wsClient.newSession();
                vscode.window.showInformationMessage('New session created');
            } catch (e: any) {
                vscode.window.showErrorMessage(e.message);
            }
        }),
        vscode.commands.registerCommand('uag.refreshTools', () => {
            treeProvider.refresh();
        }),
        vscode.window.registerTreeDataProvider('uag.tools', treeProvider)
    );

    log('INFO', 'uag extension activated successfully');
}

function log(level: string, message: string) {
    const timestamp = new Date().toISOString().slice(11, 23);
    if (outputChannel) {
        outputChannel.appendLine(`[${timestamp}][${level}] ${message}`);
    }
}

async function checkPython(pythonPath: string): Promise<boolean> {
    return new Promise((resolve) => {
        cp.exec(`"${pythonPath}" --version`, (error, stdout) => {
            if (error) {
                log('ERROR', `Python not found at "${pythonPath}"`);
                resolve(false);
            } else {
                log('INFO', `Python: ${stdout.trim()}`);
                resolve(true);
            }
        });
    });
}

async function checkUagInstalled(pythonPath: string): Promise<boolean> {
    return new Promise((resolve) => {
        cp.exec(
            `"${pythonPath}" -c "import uagent; print('ok')"`,
            (error, stdout) => {
                if (error) {
                    log('ERROR', 'uag package not found');
                    resolve(false);
                } else {
                    log('INFO', 'uag package found');
                    resolve(true);
                }
            }
        );
    });
}

async function startServer(pythonPath: string, port: number): Promise<cp.ChildProcess> {
    return new Promise((resolve, reject) => {
        const proc = cp.spawn(pythonPath, [
            '-m', 'uagent.ws_server',
            '--port', String(port),
            '--log-level', 'INFO'
        ], {
            stdio: ['ignore', 'pipe', 'pipe'],
            env: { ...process.env }
        });

        const timeout = setTimeout(() => {
            reject(new Error('Server did not start within 15 seconds'));
        }, 15000);

        let outputBuffer = '';

        proc.stdout?.on('data', (data: Buffer) => {
            const text = data.toString();
            outputBuffer += text;
            outputChannel.append(text);
            if (text.includes('UAG_WS_READY')) {
                clearTimeout(timeout);
                log('INFO', 'Server is ready');
                resolve(proc);
            }
        });

        proc.stderr?.on('data', (data: Buffer) => {
            outputChannel.append(data.toString());
        });

        proc.on('exit', (code) => {
            clearTimeout(timeout);
            log('WARN', `Server process exited with code ${code}`);
            if (code !== 0) {
                reject(new Error(`Server exited with code ${code}\n${outputBuffer}`));
            }
        });

        proc.on('error', (err) => {
            clearTimeout(timeout);
            log('ERROR', `Server process error: ${err.message}`);
            reject(err);
        });
    });
}

function runInTerminal(command: string) {
    const terminal = vscode.window.createTerminal('uag install');
    terminal.show();
    terminal.sendText(command);
}

export function deactivate() {
    log('INFO', 'uag extension deactivating...');
    wsClient?.close();
    if (serverProcess) {
        serverProcess.kill();
        serverProcess = null;
    }
    log('INFO', 'uag extension deactivated');
}
