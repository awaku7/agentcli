# enterprise-policy.yaml の編集方法

## 概要

uagのポリシー設定は、実行権限と企業固有ルールを `UnifiedPolicy` が一つにまとめて判定します。通常は `UAGENT_POLICY_FILE` のYAMLだけを管理してください。`UAGENT_POLICY_LEVEL` は開発時の一時的な権限制限に使います。

権限レベルの例:

```text
none / read_only / propose_only / write / admin
```


`enterprise-policy.yaml` は、uagで使用するツールやプロバイダーなどの動作を制御する設定ファイルです。

ツールについて、次の動作を指定できます。

- `allow`: 許可
- `deny`: 拒否
- `confirm`: 実行前に確認を要求

## ファイルの場所

### 既定の場所

`UAGENT_POLICY_FILE` 環境変数を指定していない場合、uagは次のファイルを使用します。

```text
~/.uag/enterprise-policy.yaml
```

Windowsでは通常、次の場所です。

```text
C:\Users\<ユーザー名>\.uag\enterprise-policy.yaml
```

ファイルが存在しない場合、uagが起動時に作成します。初期内容は次のとおりです。

```yaml
{}
```

`{}` はルールがない状態で、基本的にすべて許可されます。

### 別の場所を指定する場合

PowerShell:

```powershell
$env:UAGENT_POLICY_FILE = "C:\path\uagent-policy.yaml"
```

コマンドプロンプト:

```cmd
set UAGENT_POLICY_FILE=C:\path\uagent-policy.yaml
```

## 編集方法

xyzzyで既定ファイルを開く例です。

```cmd
C:\xyzzy\xyzzycli.exe C:\Users\ukawahrf\.uag\enterprise-policy.yaml
```

ファイルを編集して保存した後、必要に応じてuagを再起動します。

## 設定例

### ツールを拒否する

```yaml
tools:
  delete_file:
    action: deny
  gmail_send:
    action: deny
  browser_playwright:
    action: deny
```

### 実行前に確認する

```yaml
tools:
  bacnet_write:
    action: confirm
  matter_control:
    action: confirm
  modbus_write:
    action: confirm
```

### ツールを許可する

```yaml
tools:
  get_current_location:
    action: allow
  get_weather_wttr:
    action: allow
```

### MCPの機能(ツール)単位で確認・拒否する

`handle_mcp_v2` 経由で呼ばれる MCP サーバの個々の機能を、`server_name:tool_name` の形式で指定します。未指定の機能は従来どおり許可されます。

```yaml
mcp_tools:
  physical_vision:arm_sort:
    action: confirm   # 実機アームを動かす機能は人手承認が必要
  physical_vision:erase:
    action: deny      # この機能は常に拒否
```

### 複数のルールを組み合わせる

```yaml
tools:
  delete_file:
    action: deny
  gmail_send:
    action: deny
  bacnet_write:
    action: confirm
  get_weather_wttr:
    action: allow
```

## 注意点

- YAMLのインデントにはスペースを使用します。
- `tools:` の配下は2スペースでインデントします。
- ツール名は正確に指定します。
- `mcp_tools:` のキーは `サーバ名:機能名`(例: `physical_vision:arm_sort`)で指定します。
- `deny` は実行を拒否します。
- `confirm` は通常の確認フローを要求します。
- `allow` は明示的に許可します。
- `{}` に戻すとルールなしの状態になります。
- Policyは主にツールの実行・呼び出しを制御します。起動時に有効化するジャンルは、別途 `--tool-genre-mask` で指定します。

## 起動時のツール有効化との併用

起動時にジャンルを有効化しない場合:

```cmd
uag --tool-genre-mask 0
```

必要なツールだけ個別に有効化する場合:

```cmd
uag --tool-genre-mask 0 --enable-tool get_current_location --enable-tool get_weather_wttr
```

Policyで拒否したツールは、起動時に有効化しても実行できません。
