# ツール別 `absconfirm` 設定

## 目的

通常、auto-pilotや注入モードでは、`human_ask` による質問・確認をスキップして自律実行します。

危険な処理や機器操作など、特定のツールだけは `absconfirm` を指定すると、実行前に必ずユーザー確認を要求できます。

## 設定ファイル

設定は `enterprise-policy.yaml` に記述します。

## MCP機能を個別に確認する

MCPの呼び出しは `handle_mcp_v2` を経由しますが、MCPサーバー名と機能名を指定して、特定のMCP機能だけを確認対象にできます。

```yaml
auto_pilot:
  mcp_tools:
    physical_vision:arm_sort: absconfirm

inject_message:
  mcp_tools:
    physical_vision:arm_sort: absconfirm
```

`physical_vision:arm_sort` は次の2つを結合した識別子です。

- `physical_vision`：MCPサーバー名（`server_name`）
- `arm_sort`：MCP機能名（`tool_name`）

この設定では、`arm_sort` の実行前だけ確認が表示されます。`scan_and_judge` など、未指定の機能は確認されません。

## まず覚えること

`--inject-message-auto` だけで確認したい場合は、`inject_message` だけに書けば十分です。

```yaml
inject_message:
  mcp_tools:
    physical_vision:arm_sort: absconfirm
```

`--inject-message-auto` は「注入モード」であり、同時にauto-pilotを開始しますが、確認設定は `inject_message` 側が使われます。

通常の `:auto` でも同じ確認をしたい場合だけ、`auto_pilot` 側にも書きます。

```yaml
auto_pilot:
  mcp_tools:
    physical_vision:arm_sort: absconfirm
```

つまり、次の対応関係です。

| 起動方法 | 使用する設定 |
|---|---|
| `:auto` | `auto_pilot` |
| `--inject-message` | `inject_message` |
| `--inject-message-auto` | `inject_message` |

## モード別の設定

### auto-pilotだけで確認する

```yaml
auto_pilot:
  mcp_tools:
    physical_vision:arm_sort: absconfirm
```

`:auto` および `--inject-message-auto` で確認されます。

### 注入モードだけで確認する

```yaml
inject_message:
  mcp_tools:
    physical_vision:arm_sort: absconfirm
```

`--inject-message` および `--inject-message-auto` で確認されます。

### 両方で確認する

```yaml
auto_pilot:
  mcp_tools:
    physical_vision:arm_sort: absconfirm

inject_message:
  mcp_tools:
    physical_vision:arm_sort: absconfirm
```

## MCP全体を確認対象にする

MCP機能を個別に指定せず、`handle_mcp_v2` 経由のすべての呼び出しを確認対象にする場合は、次のようにします。

```yaml
auto_pilot:
  tools:
    handle_mcp_v2: absconfirm
```

注入モードの場合は `inject_message.tools` に指定します。

```yaml
inject_message:
  tools:
    handle_mcp_v2: absconfirm
```

## 通常モードでも確認する

通常モード、auto-pilot、注入モードのすべてで確認する場合は、それぞれ指定します。

```yaml
mcp_tools:
  physical_vision:arm_sort:
    action: confirm

auto_pilot:
  mcp_tools:
    physical_vision:arm_sort: absconfirm

inject_message:
  mcp_tools:
    physical_vision:arm_sort: absconfirm
```

設定の役割は次のとおりです。

- `mcp_tools`：通常モードでの確認
- `auto_pilot.mcp_tools`：auto-pilot中の確認
- `inject_message.mcp_tools`：`--inject-message(-auto)` 中の確認

## `absconfirm` の動作

- 指定されたツールだけ、実行前に確認する
- `yes` / `y` で実行を許可する
- `no`、`c`、キャンセル、タイムアウトでは実行しない
- 確認の既定タイムアウトは300秒。`UAGENT_HUMAN_ASK_TIMEOUT_SEC` で変更できる
- 未指定のツールは、各モードの従来の動作に従う
- `absconfirm` はMCP以外のツールにも使用できる

例：

```yaml
auto_pilot:
  tools:
    delete_file: absconfirm

inject_message:
  tools:
    rename_path: absconfirm
```

## 注意事項

`absconfirm` は「そのモードで確認を必須にする」設定です。確認を自動的に `yes` とする設定ではありません。

`--inject-message` と `--inject-message-auto` は通常は非対話モードですが、対象ツールに `inject_message` の `absconfirm` を指定した場合は、標準入力で確認を待ちます。標準入力を利用できない環境では、確認できないため安全側で実行されません。
