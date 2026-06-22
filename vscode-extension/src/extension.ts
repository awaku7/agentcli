import * as vscode from 'vscode';

let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel('uag');
    log('INFO', 'uag extension activating...');

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('uag.chat', () => {
            vscode.window.showInformationMessage('uag: Chat panel - coming soon');
        }),
        vscode.commands.registerCommand('uag.explain', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const selection = editor.document.getText(editor.selection);
            log('INFO', `Explain: ${selection.length} chars selected`);
            vscode.window.showInformationMessage('uag: Explain - coming soon');
        }),
        vscode.commands.registerCommand('uag.refactor', () => {
            vscode.window.showInformationMessage('uag: Refactor - coming soon');
        }),
        vscode.commands.registerCommand('uag.fix', () => {
            vscode.window.showInformationMessage('uag: Fix - coming soon');
        }),
        vscode.commands.registerCommand('uag.newSession', () => {
            vscode.window.showInformationMessage('uag: New Session - coming soon');
        })
    );

    log('INFO', 'uag extension activated');
}

function log(level: string, message: string) {
    const timestamp = new Date().toISOString().slice(11, 23);
    outputChannel.appendLine(`[${timestamp}][${level}] ${message}`);
}

export function deactivate() {
    log('INFO', 'uag extension deactivated');
}
