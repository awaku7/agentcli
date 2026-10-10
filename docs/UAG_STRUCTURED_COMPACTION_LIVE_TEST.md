# UAG Structured Compaction 実LLM検証手順

- **実施予定日:** 2026-10-12（日本時間）
- **対象:** [PR #226](https://github.com/awaku7/agentcli/pull/226)（CLIからの構造化Checkpoint永続保存・動的圧縮範囲）および [PR #228](https://github.com/awaku7/agentcli/pull/228)（圧縮開始トークン上限の共通設定化）
- **対象環境:** Windows / Python 3.14 / 通常の対話型CLI / 実LLM（普段のOpenAIモデルを想定）
- **現在の判定:** **未実施**。本書は当日の手順・記録用であり、実LLM動作の成功を宣言するものではない。
- **既存仕様の参照先:** [実装記録](./UAG_STRUCTURED_COMPACTION_IMPLEMENTATION.md) / [圧縮の説明](./CONTEXT_COMPRESSION.ja.md)

## 1. 検証の目的

通常CLIで`UAGENT_STRUCTURED_COMPACTION=1`にしたとき、次の6項目を実LLMで確認する。

1. 初回圧縮でSQLiteの`checkpoints`へ`applied`レコードが保存される。
2. 圧縮後の新しい会話だけが次のCheckpointの出典範囲になる（旧履歴の再適用なし）。
3. 圧縮以前に確定した複数の事実・制約を正しく回答できる。
4. 構造化圧縮がSQLiteの`messages`（Raw History）を書き換え・削除しない。
5. 同じセッションを終了・再起動・読み込みした後も作業を継続できる。
6. ツール呼び出しと結果の対応が維持され、ツールを伴うターンも正常に終了する。

これは**通常CLIでの構造化圧縮**の検証であり、Sub-Agent handoff、Auto-pilotの再開、GUI/Web/A2A、複数Clientの競合処理は対象外とする。

## 2. 前提・準備

1. 未コミットの変更がある場合は事前に退避する。以下は既存の`main`を更新できる状態を想定する。
2. APIキーおよびプロバイダ・モデルは普段の設定（`.env`など）を使用する。機密情報をログや検証結果に貼り付けない。
3. **テスト専用のSQLiteファイル名**を使い、普段のセッションDBと分離する。指定先に既存ファイルがある場合は別の名前を選ぶ（無断で削除しない）。

Windowsの**コマンドプロンプト（cmd.exe）**で実行する。

```bat
cd /d F:\KAIHATSU\agentcli
git switch main
git pull --ff-only
python -m pip install -e .
```

同じcmdウィンドウで、実行時の環境変数を設定する。

```bat
set "UAGENT_SESSION_STORE=1"
set "UAGENT_SESSION_STORE_PATH=%TEMP%\uag-structured-compaction-20261012.sqlite3"
set "UAGENT_STRUCTURED_COMPACTION=1"
set "UAGENT_SHRINK_CNT=6"
set "UAGENT_SHRINK_KEEP_LAST=2"
set "UAGENT_SHRINK_MAX_TOKENS=0"
set "UAGENT_SHRINK_CHUNK_TOKENS=12000"
set "UAGENT_SUMMARY_ON_EXIT=0"
```

事前確認（既存DBなら別名を選ぶ）。

```bat
if exist "%UAGENT_SESSION_STORE_PATH%" echo WARNING: Test DB already exists. Use a new filename.
```

**設定の意味:**

- `UAGENT_SHRINK_CNT=6`：少ないターン数で初回圧縮を試す。
- `UAGENT_SHRINK_KEEP_LAST=2`：直近2メッセージを圧縮対象から保護する。
- `UAGENT_SHRINK_MAX_TOKENS=0`：**トークン数による圧縮開始判定を抑止**する。対応するResponsesのサーバー側圧縮もこのしきい値では有効にならず、ローカル構造化圧縮の件数発動を観測しやすくする。
- `UAGENT_SHRINK_CHUNK_TOKENS=12000`：構造化要約を作るときの入力トークン予算の上限。**圧縮を開始する条件とは別**。
- `UAGENT_SUMMARY_ON_EXIT=0`：終了時の別系統の要約処理を抑え、検証条件を単純化する。

**PR #228以降:** `UAGENT_SHRINK_MAX_TOKENS`は**共通の整数設定だけ**。`UAGENT_SHRINK_MAX_TOKENS_GPT_6_LUNA`などのモデル別環境変数や、JSONによるモデル別指定は使用しない。共通設定未指定ならllmcapaから既定値を算出する。

この設定でも圧縮は安全なターン境界でだけ実行されるため、「入力6回目で必ずCheckpointができる」とは限らない。また、出典の正確な並びを検証できない場合や構造化生成に失敗した場合は、Checkpointを確定しない。

## 3. 初回のCheckpoint保存

```bat
python -m uagent
```

次の5つを**1件ずつ、応答を待ってから**送信する。通常の会話として扱い、`add_long_memory`等への保存は依頼しない。

```text
検証案件K17は在庫管理システムの開発です。
```

```text
検証案件K17ではPython 3.14を使用します。
```

```text
データベースはSQLiteを使用し、PostgreSQLは使いません。
```

```text
画面はWeb UIとし、デスクトップアプリは作りません。
```

```text
これまでの検証案件K17の決定事項を整理してください。
```

必要ならさらに数ターン、設計の決定事項について対話を追加する。圧縮成功時にはCLIに以下のような情報が表示される場合がある。

```text
[INFO] structured compaction: ... messages ...
```

ただし**ログがないことだけでは失敗と判定しない**。Checkpointの永続保存はSQLiteで確認する。

## 4. SQLiteで永続保存を確認

検証用のDBを参照する。別のcmdを使っても同じ`%TEMP%`のファイルを参照する。

以下は**読み取りだけ**を行う。`checkpoints`の`application_status`が`applied`となっているか、出典の`source_start_seq` / `source_end_seq`がどう推移したかを確認する。

```bat
python -c "import os,sqlite3; p=os.path.join(os.environ['TEMP'],'uag-structured-compaction-20261012.sqlite3'); c=sqlite3.connect(p); print('DB:',p); print('Raw messages:',c.execute('SELECT COUNT(*) FROM messages').fetchone()[0]); print('Checkpoints:',c.execute('SELECT session_id, application_status, source_start_seq, source_end_seq, result_revision FROM checkpoints ORDER BY session_id, source_start_seq').fetchall()); c.close()"
```

期待結果:

- `Checkpoints:` に少なくとも1件の`applied`がある。
- `Raw messages:` には元の発言が残る。
- チェックポイントがない場合、**原因を調べるまで未確認扱い**にする（生成失敗、しきい値未到達、異なるDBを開いた、サーバー側圧縮の優先、出典不整合など）。

元の重要事項が残っているかも確認する。

```bat
python -c "import os,sqlite3; p=os.path.join(os.environ['TEMP'],'uag-structured-compaction-20261012.sqlite3'); c=sqlite3.connect(p); print(c.execute('SELECT message_id, role, content FROM messages WHERE content LIKE ?',('%検証案件K17%',)).fetchall()); c.close()"
```

この出力には会話本文が含まれる。共有するときは私的情報や機密情報を除去する。

## 5. 継続圧縮・出典重複の確認

**同じセッションで**、検証案件K17について設計上の小さな決定事項を追加して会話を続ける。目安は6往復前後だが、必ずその回数で圧縮されるわけではない。

既存Checkpointがある場合、再圧縮の件数基準にはヒステリシスがあり、この設定では`max(KEEP_LAST*2, KEEP_LAST+10, SHRINK_CNT) = 12`件の**新しい履歴**が一つの目安になる。

再度、前節のSQLite確認コマンドを実行する。**同じセッションIDの`applied` Checkpointが2件以上**になったら、出典範囲の並びを比較する。

```text
前のCheckpoint: source_start_seq = A, source_end_seq = B
次のCheckpoint: source_start_seq = C, source_end_seq = D
期待値: C > B
```

2件目のCheckpointが増えない場合は、単に「失敗」とせず、出典の新規件数とログを確認する。

## 6. 圧縮前の決定事項を回答できるか

同じセッションで質問する。

```text
検証案件K17について、使用言語、使用するDB、使わないDB、画面方式を教えてください。この会話で決めた内容だけを根拠にしてください。
```

期待する内容は**Python 3.14、SQLite、PostgreSQLは使わない、Web UI**の4点。長期Memoryからの再取得とは区別し、あくまで会話継続の確認として判定する。

## 7. セッション終了・再起動・復元

1. `:sessions list`で対象セッションIDを控える。
2. `:exit`でCLIを終了する。
3. **同じ検証用SQLiteと環境変数**のままCLIを再起動する（別のcmdで起動する場合は第2節の`set`を再設定）。
4. `:sessions load <session_id>`で該当セッションを開く。
5. 第6節の質問をもう一度行い、4点が保持されているか確かめる。
6. SQLiteの`applied` Checkpoint数・出典範囲・Raw messagesも再確認する。**復元だけで同じ古い履歴を再圧縮してCheckpointが増えることを期待しない。**

`:sessions resume`は移植用パッケージのコマンドであり、今回の通常セッション再開には使用しない。

## 8. ツール呼び出しを含む会話

復元後の**同じセッション**で次を依頼する。

```text
現在日時を取得するツールを使い、続けてPythonで17×23を計算してください。両方の結果をまとめてください。
```

期待結果:

- 計算結果は`391`。
- 実際に使われたツール呼び出しと応答の対応が取れており、孤立した結果・プロバイダ側のcall ID不整合によるエラーがない。
- さらに履歴を蓄積して圧縮が発動した場合も、ツールの実行結果が別の呼び出しへ誤って結び付かない。

ツールが選択されずLLMが文章だけで回答した場合、**ツール連続実行の検証は未実施**として扱い、ツールの有効化状態を確認する。

## 9. 合否判定・障害時の情報

| 項目 | 合格条件 | 結果 |
|---|---|---|
| 初回Checkpoint | `applied`が1件以上保存される | 未実施 |
| 継続Checkpoint | 同一セッションに2件以上、後続の`source_start_seq > 前回のsource_end_seq` | 未実施 |
| 内容保持 | 4つの決定事項を正確に回答 | 未実施 |
| Raw History | 過去のメッセージが消えずに参照できる | 未実施 |
| 再起動・復元 | 元のセッションを開き、決定事項を回答できる | 未実施 |
| ツール対応 | 複数のツール呼び出しと結果が対応し、正常に終了 | 未実施 |

問題が起きたときは、次を記録する。

- 使用したコミットSHA（`git rev-parse HEAD`）、Pythonバージョン、Provider、Model、Responses API使用有無
- 使用した`UAGENT_SHRINK_*`および`UAGENT_STRUCTURED_COMPACTION`設定（APIキーは記録しない）
- 再現した入力・CLI出力のうち必要な部分、エラーとその直前の操作
- `checkpoints`の件数・状態・`source_start_seq` / `source_end_seq` / revision
- `messages`の件数と、該当する旧発言が残っているか
- 再起動の前後やツール実行の前後、どの段階で挙動が変わったか

失敗があっても、**原因が確定する前に圧縮ロジックをまとめて書き換えない**。一つずつ事象を再現・切り分けて修正する。

## 10. 検証記録（当日記入）

| 項目 | 記録 |
|---|---|
| 実施日時 | |
| `main`コミットSHA | |
| Python / Provider / Model | |
| Responses API使用有無 | |
| 初回Checkpoint数・source range | |
| 継続Checkpoint数・source range | |
| Raw messages件数（前／後） | |
| 記憶の回答結果 | |
| 再起動後の回答結果 | |
| ツール実行の結果 | |
| 警告・エラー・未確認事項 | |
| 総合判定（合格／不合格／保留） | |

## 11. 検証後の環境

環境変数`set`は通常、設定したcmdプロセスに限って有効。通常運用に戻る際は、その検証用cmdを閉じればよい。検証用DBは結果の再確認が終わるまで保持し、普段のセッションDBにはコピーしない。
