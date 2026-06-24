import * as vscode from 'vscode';
import { WsClient } from './wsClient';

export class EditorIntegration {
    constructor(private ws: WsClient) {}

    async explainSelection(): Promise<void> {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('No active editor');
            return;
        }
        const selection = editor.document.getText(editor.selection);
        if (!selection) {
            vscode.window.showInformationMessage('No text selected');
            return;
        }
        const filePath = editor.document.uri.fsPath;
        const language = editor.document.languageId;
        const message = [
            'Explain this code from ' + filePath + ':',
            '',
            '```' + language,
            selection,
            '```',
            '',
            'Provide a clear explanation of what this code does.'
        ].join('\n');
        await this.sendToChat(message);
    }

    async refactorSelection(): Promise<void> {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('No active editor');
            return;
        }
        const selection = editor.document.getText(editor.selection);
        if (!selection) {
            vscode.window.showInformationMessage('No text selected');
            return;
        }
        const filePath = editor.document.uri.fsPath;
        const language = editor.document.languageId;
        const message = [
            'Refactor this code from ' + filePath + ':',
            '',
            '```' + language,
            selection,
            '```',
            '',
            'Please refactor the code to improve readability, performance, and maintainability.',
            'Output the refactored code in a code block and explain your changes.'
        ].join('\n');
        const { ChatPanel } = require('./panel');
        const ctx = this.getExtensionContext();
        if (ctx) {
            ChatPanel.createOrShow(ctx, this.ws);
        }
        try {
            const result = await this.ws.call('chat', { message: message }, 300000);
            const reply = (result.reply || '') as string;
            const refactoredCode = this.extractCodeBlock(reply);
            if (refactoredCode) {
                const action = await vscode.window.showInformationMessage(
                    'uag: リファクタリング案があります',
                    'Show Diff',
                    'Apply'
                );
                if (action === 'Show Diff' || action === 'Apply') {
                    const edit = new vscode.WorkspaceEdit();
                    edit.replace(editor.document.uri, editor.selection, refactoredCode);
                    await vscode.workspace.applyEdit(edit);
                    if (action === 'Apply') {
                        vscode.window.showInformationMessage('リファクタリングを適用しました: ' + filePath);
                    }
                }
            } else {
                vscode.window.showInformationMessage('レスポンスからコードブロックを抽出できませんでした');
            }
        } catch (e: any) {
            vscode.window.showErrorMessage('リファクタリングに失敗しました: ' + e.message);
        }
    }

    async fixError(): Promise<void> {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('No active editor');
            return;
        }
        const document = editor.document;
        const position = editor.selection.active;
        const diagnostics = vscode.languages.getDiagnostics(document.uri);
        const errorsAtCursor = diagnostics.filter(d => d.range.contains(position));

        if (errorsAtCursor.length === 0) {
            vscode.window.showInformationMessage('No errors at cursor position');
            return;
        }

        const errorText = errorsAtCursor.map(d =>
            '  - Line ' + (d.range.start.line + 1) + ': [' + (d.severity === vscode.DiagnosticSeverity.Error ? 'ERROR' : 'WARNING') + '] ' + d.message
        ).join('\n');

        const code = document.getText();
        const filePath = document.uri.fsPath;
        const language = document.languageId;
        const message = [
            'Fix the following errors in ' + filePath + ':',
            '',
            errorText,
            '',
            'Full source code:',
            '```' + language,
            code,
            '```',
            '',
            'Output the complete fixed file content in a single code block.'
        ].join('\n');

        const { ChatPanel } = require('./panel');
        const ctx = this.getExtensionContext();
        if (ctx) {
            ChatPanel.createOrShow(ctx, this.ws);
        }

        try {
            const result = await this.ws.call('chat', { message: message });
            const reply = (result.reply || '') as string;
            const fixedCode = this.extractCodeBlock(reply);

            if (fixedCode) {
                const action = await vscode.window.showInformationMessage(
                    'uag: Suggested fix available',
                    'Show Diff',
                    'Apply'
                );
                if (action === 'Show Diff' || action === 'Apply') {
                    const uri = document.uri;
                    const fullRange = new vscode.Range(
                        document.positionAt(0),
                        document.positionAt(code.length)
                    );
                    const edit = new vscode.WorkspaceEdit();
                    edit.replace(uri, fullRange, fixedCode);
                    await vscode.workspace.applyEdit(edit);
                    if (action === 'Apply') {
                        vscode.window.showInformationMessage('Fix applied to ' + filePath);
                    }
                }
            } else {
                vscode.window.showInformationMessage('Could not extract code block from the response');
            }
        } catch (e: any) {
            vscode.window.showErrorMessage('Failed to get fix: ' + e.message);
        }
    }

    async sendToChat(text: string): Promise<void> {
        const { ChatPanel } = require('./panel');
        const ctx = this.getExtensionContext();
        if (!ctx) {
            vscode.window.showErrorMessage('Extension context not available');
            return;
        }
        const panel = ChatPanel.createOrShow(ctx, this.ws);
        panel.sendChatMessage(text);
    }

    getExtensionContext(): vscode.ExtensionContext | null {
        const ctx = (global as any).__uag_extension_context;
        return ctx || null;
    }

    private extractCodeBlock(text: string): string | null {
        const match = text.match(/```\w*\n?([\s\S]*?)\n?```/);
        if (match && match[1]) {
            return match[1].trim();
        }
        return null;
    }
}
