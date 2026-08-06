# n8n連携

- Status: planned
- Priority: P1
- Source: [`docs/n8n/README.md`](../n8n/README.md)

## Phase 0

- n8n Instance-level MCPを有効化
- 検証WorkflowだけをMCP公開
- uagからMCP tools list、検索、Workflow実行を確認
- n8nからuag A2Aへping
- トークンをGit管理下に含めない

## Phase 1以降

- 公開Workflowの最小集合化
- description整備
- 危険操作の二重確認
- correlation ID / max depthによるループ防止
- MCPで不足する場合のみ専用`n8n_*`ツールを設計
