# Sub-Agent 権限レベルのテスト手順

## 目的と範囲

`run_sub_agent` の `permission_level` が、ツールスキーマの提示時と実行時の両方で適用されることを確認する。対象は `none`、`read_only`、`propose_only` の3段階であり、特に native tool calling と互換（テキスト解析）経路のどちらからも権限を迂回できないことを検証する。

この手順は、通常の自動テストと、実プロバイダを使う任意の対話型スモークテストを分けている。スモークテストでは破壊的な操作を実行せず、テスト用ファイルだけを対象にする。

## 前提

- リポジトリのルートで作業する。
- Python の開発依存関係と、プロジェクトが通常使用する環境設定が済んでいる。
- 実プロバイダを使うスモークテストでは、使用するプロバイダの認証・モデル設定を事前に確認する。
- テスト対象に実データ、既存ファイル、秘密情報を使わない。

## 1. 自動テスト

Windows PowerShell では、リポジトリルートで次を実行する。

```powershell
$env:UAGENT_NON_INTERACTIVE = "1"
$env:UAGENT_CONFIRM_TOOLS = "0"
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_sub_agent_permissions.py
```

期待結果: permission test がすべて成功する。テストでは次を確認する。

- `read_only` は限定された読取ツールのみを実行し、書込系ツールを拒否する。
- `propose_only` の `create_file` は提案結果を返すだけで、runnerを呼ばずにファイルを作成しない。
- `overwrite=True` と削除などの変更操作は拒否される。
- native tool schema が permission level と role の allowlist で絞られる。
- 未知の権限値は `none` 相当として fail closed になる。
- native tool call で許可外ツールを直接要求しても、実行されない。

回帰確認として、必要に応じてリポジトリ全体のテストを実行する。

```powershell
python -m pytest -q tests
```

期待結果: 終了コード `0`。skip は環境依存テストのために設定されたものとして扱い、失敗があれば個別に調査する。

## 2. 任意の対話型スモークテスト

この確認は実プロバイダと対話可能な CLI / Web / GUI 環境で行う。該当する環境がない場合は省略し、その旨を記録する。ツールの実行ログが見える場合は、Sub-Agent が呼び出したツール名と結果も確認する。

### 2.1 `read_only` の許可された読取

Main Agent に、次の依頼を行う。

> `run_sub_agent` を `agent_name="general"`、`permission_level="read_only"` で実行してください。タスクは `read_file(filename="README.md", maxl=5)` を使ってREADMEの先頭5行を読み、短く要約することです。ファイル変更や他の副作用のある操作はしないでください。

確認事項:

- Sub-Agent が `read_file` を使って先頭5行を確認し、その内容に沿った要約を返す。
- ファイル変更がない。
- 実行ログが利用できる場合、読取ツールが成功している。

### 2.2 `read_only` の拒否

存在する重要ファイルではなく、先に用意した使い捨てのテストファイル（例: `tmp/subagent-permission-probe.txt`）を対象に、次の依頼を行う。テストファイルはスモークテスト実行者が作成し、内容を記録しておく。

> `run_sub_agent` を `agent_name="general"`、`permission_level="read_only"` で実行してください。タスク内で `delete_file(filename="tmp/subagent-permission-probe.txt")` を試みてください。許可されない場合は、その理由を報告してください。ほかの操作はしないでください。

確認事項:

- 削除が `blocked` / 権限拒否になる。
- テストファイルが存在し、内容も実行前と変わらない。
- 拒否された操作が成功扱いにならない。

### 2.3 `propose_only` の新規ファイル提案

存在しない一意なパス（例: `tmp/subagent-proposal-<run-id>.txt`）を決めて、次の依頼を行う。

> `run_sub_agent` を `agent_name="general"`、`permission_level="propose_only"` で実行してください。`create_file(filename="tmp/subagent-proposal-<run-id>.txt", content="permission proposal test", overwrite=False)` を提案してください。提案以外の操作やファイル作成はしないでください。

確認事項:

- 結果が `proposed` で、`executed: false` を示す。
- 指定したパスにファイルが実際には作成されていない。
- runner がファイル作成を実行していない。

### 2.4 `propose_only` の上書き・削除拒否

2.2で用意した使い捨てファイルを使い、次の依頼を行う。

> `run_sub_agent` を `agent_name="general"`、`permission_level="propose_only"` で実行してください。テストファイルへの `create_file(..., overwrite=True)` と `delete_file(...)` は、実行せずに権限拒否として報告してください。

確認事項:

- 上書き提案と削除が拒否される。
- テストファイルの内容が実行前と一致する。

### 2.5 `none` と不明な権限値

- `permission_level="none"` でツールを必要とするタスクを実行し、ツールが実行されず、その旨が回答に示されることを確認する。
- 通常の公開インターフェースで許可されない不明な権限値を試す場合は、実運用の外部ツールを使わず、自動テストの fail-closed ケースを正とする。未知値が何らかの形でランタイムに渡った場合も、権限が広がってはならない。

## 3. 合否基準

以下をすべて満たせば合格。

1. 対象の pytest が成功する。
1. 読取許可ツールは指定範囲の情報を返す。
1. 許可されない操作は拒否され、実ファイルの状態に変化がない。
1. `propose_only` の新規作成は提案として返り、ファイルを作成しない。
1. native / compatibility のいずれの呼び出し経路でも、実行時 gate が適用される。

失敗した場合は、使用した permission level、provider/model、実行環境、Sub-Agent のツール呼び出し記録、テストファイルの実行前後の状態を記録する。秘密情報や認証情報はログへ記載しない。

## 4. 実施記録テンプレート

```text
日時:
ブランチ / commit:
Python / OS:
自動テスト結果:
スモークテスト実施環境（CLI / Web / GUI / 未実施）:
permission level ごとの結果:
テストファイルの実行前後の状態:
失敗内容・関連ログ（秘密情報を除く）:
```
