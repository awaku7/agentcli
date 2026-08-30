# `set_timer`

`set_timer` は永続的なワンショットタイマーを作成・一覧表示・削除します。
タイマーはSchedulerに保存され、指定時刻にLLMへプロンプトを入力できます。

## LLM実行

```json
{
  "seconds": 60,
  "message": "Timer finished",
  "on_timeout_prompt": "デプロイ状況を確認してください",
  "required_tools": ["workspace_status"],
  "execution_mode": "llm"
}
```

`required_tools` に指定したツールは、スケジュールされたLLM実行中だけロードして
pinされます。実行後は、実行前のpin状態に戻ります。

## 直接ツール実行

LLMラウンドを実行せず、1つの明示的なツールをタイマーから直接実行できます。

```json
{
  "seconds": 300,
  "execution_mode": "direct",
  "target_tool": "workspace_status",
  "target_args": {}
}
```

直接実行でも通常のツールディスパッチとポリシーチェックが適用されます。
管理ツールや任意コード実行ツールは直接実行対象にできません。
`direct` と `os_persist=true` の併用はできません。OSジョブは別プロセスで
`uag`を起動するため、通常の注入メッセージ経路を使用します。

## 一覧表示と削除

`{"action":"list"}` で内部タイマーとOSタイマーを一覧表示します。
内部タイマーには `schedule_id` が表示されるので、
`{"action":"delete", "schedule_id":"..."}` で削除できます。
OSタイマーは `job_name` で削除します。

リトライ回数、タイムアウト、required toolのメタデータも実行情報とともに保存されます。
失敗・タイムアウトした実行は `SchedulerRunStore` に最終状態として記録されます。
