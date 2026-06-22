import * as vscode from 'vscode';
import * as cp from 'child_process';
import { WsClient } from './wsClient';
import { ChatPanel } from './panel';
import { ToolTreeProvider } from './treeProvider';

let wsClient: WsClient;
let outputChannel: vscode.OutputChannel;
let serverProcess: cp.ChildProcess | null = null;
let statusBarItem: vscode.StatusBarItem;

export async function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel('uag');
    log('INFO', 'uag extension activating...');

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

    // Start WebSocket server
    const port = vscode.workspace.getConfiguration('uag')
        .get<number>('port', 18765);
    statusBarItem.text = '$(hubot) uag: connecting...';
    serverProcess = startServer(pythonPath, port);

    // Connect WebSocket client
    wsClient = new WsClient();

    // Update status on connection change
    wsClient.onDidChangeStatus((connected) => {
        statusBarItem.text = connected
            ? '$(hubot) uag: connected'
            : '$(warning) uag: disconnected';
        if (connected) {
            // Set workdir to current workspace folder
            const folders = vscode.workspace.workspaceFolders;
            if (folders) {
                wsClient.setWorkdir(folders[0].uri.fsPath).catch(() => {});
            }
        }
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

    // Tool tree view
    const treeProvider = new ToolTreeProvider(wsClient);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('uag.chat', () => {
            ChatPanel.createOrShow(context, wsClient);
        }),
        vscode.commands.registerCommand('uag.explain', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const selection = editor.document.getText(editor.selection);
            if (!selection) {
                vscode.window.showInformationMessage('No text selected');
                return;
            }
            ChatPanel.createOrShow(context, wsClient);
            vscode.window.showInformationMessage(
                `Selected ${selection.length} chars for explanation`
            );
        }),
        vscode.commands.registerCommand('uag.refactor', async () => {
            vscode.window.showInformationMessage('Refactor - coming in Phase 2');
        }),
        vscode.commands.registerCommand('uag.fix', async () => {
            vscode.window.showInformationMessage('Auto-fix - coming in Phase 2');
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

function startServer(pythonPath: string, port: number): cp.ChildProcess {
    const proc = cp.spawn(pythonPath, [
        '-m', 'uagent.ws_server',
        '--port', String(port),
        '--log-level', 'INFO'
    ], {
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env }
    });

    proc.stdout?.on('data', (data: Buffer) => {
        outputChannel.append(data.toString());
    });

    proc.stderr?.on('data', (data: Buffer) => {
        outputChannel.append(data.toString());
    });

    proc.on('exit', (code) => {
        log('WARN', `Server process exited with code ${code}`);
    });

    proc.on('error', (err) => {
        log('ERROR', `Server process error: ${err.message}`);
    });

    return proc;
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
