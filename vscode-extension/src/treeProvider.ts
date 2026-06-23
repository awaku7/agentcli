import * as vscode from 'vscode';
import { WsClient } from './wsClient';

class ToolItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly genre: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly toolSpec?: any
    ) {
        super(label, collapsibleState);
        if (toolSpec) {
            this.description = (toolSpec.description || '').slice(0, 60);
            this.tooltip = toolSpec.description || '';
            this.contextValue = 'tool';
            this.iconPath = this.getIcon(toolSpec.genre);
        } else {
            this.contextValue = 'genre';
            this.iconPath = new vscode.ThemeIcon('folder');
        }
    }

    private getIcon(genre: string): vscode.ThemeIcon {
        const iconMap: Record<string, string> = {
            'file': 'file',
            'comm': 'symbol-misc',
            'iot': 'plug',
            'devel': 'tools',
            'exec': 'terminal',
            'media': 'device-camera',
            'office': 'book',
            'basic': 'symbol-property',
            'external': 'link',
        };
        return new vscode.ThemeIcon(iconMap[genre] || 'symbol-method');
    }
}

export class ToolTreeProvider implements vscode.TreeDataProvider<ToolItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<ToolItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    private tools: any[] = [];

    constructor(private ws: WsClient) {
        this.refresh();
        ws.onDidChangeStatus((connected) => {
            if (connected) this.refresh();
        });
    }

    async refresh(): Promise<void> {
        try {
            if (this.ws.isConnected) {
                this.tools = await this.ws.listTools();
            } else {
                this.tools = [];
            }
        } catch {
            this.tools = [];
        }
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: ToolItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: ToolItem): Promise<ToolItem[]> {
        if (!element) {
            // Root: genre categories
            const genres = new Map<string, any[]>();
            for (const t of this.tools) {
                const g = t.genre || 'other';
                if (!genres.has(g)) genres.set(g, []);
                genres.get(g)!.push(t);
            }
            const items: ToolItem[] = [];
            for (const [genre, tools] of genres) {
                items.push(new ToolItem(
                    this.capitalize(genre),
                    genre,
                    vscode.TreeItemCollapsibleState.Collapsed
                ));
            }
            return items;
        } else {
            // Children: tools in this genre
            const tools = this.tools.filter(t => (t.genre || 'other') === element.genre);
            return tools.map(t => new ToolItem(
                t.name,
                t.genre,
                vscode.TreeItemCollapsibleState.None,
                t
            ));
        }
    }

    private capitalize(s: string): string {
        return s.charAt(0).toUpperCase() + s.slice(1);
    }
}
