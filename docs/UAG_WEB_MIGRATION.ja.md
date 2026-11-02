# UAG Web 独立化: 調査と段階的移行設計

## 調査基準と現在の状態

調査基準は main の `7523ee1a9a4d238ba0a964862c9eecdba8f58e05`
（uag 0.7.41）。依存関係とHTTPルートの機械抽出結果は
[インベントリ](UAG_WEB_MIGRATION_INVENTORY.json)に記録した。
これは移行完了報告ではない。旧Webは独立版の受け入れ完了まで維持する。

GitHubからagentcliを取得し、読み書き権限を確認した。
`awaku7/uag-web` は接続済みAPIでは404。
`gh repo create awaku7/uag-web --public` は
`Resource not accessible by integration (createRepository)` で拒否された。
GitHubでの新リポジトリ作成・そのリポジトリへのPR作成は未完了。
作成権限を持つ接続またはユーザーによる空リポジトリ作成が必要。

## 責務と移行対象

| 対象 | 移行先 / 方針 |
| --- | --- |
| `frontend/` 全体 | uag-web。Svelte 5 / Vite 6。UIの再設計はしない |
| `src/uagent/web.py` | `uag_web/server.py` の起動・ルート読み込み。旧import面は最終的に削除 |
| `web_impl/app.py` | `uag_web/app.py`。FastAPI、リソース配置、HTTPミドルウェア |
| `web_impl/init.py` | uag-web。Web起動、既存UAG初期化呼び出し、UIフック設定 |
| `web_impl/routes_*.py` | uag-web。既存URL・応答・認証順序を維持 |
| `web_impl/rooms.py`, `connection_identity.py` | uag-web。接続とルーム管理、共通アクセス制御APIの利用 |
| `web_impl/io.py`, `helpers.py`, `history.py` | uag-web。表示、ストリーム、履歴投影。Memory実装は移さない |
| `web_impl/agent_worker.py` | uag-webのホストアダプター。LLMラウンドは既存UAGに委譲 |
| `web_impl/process_workers.py`, `sandbox_rpc.py` | uag-web。既存spawn/IPCのルーム分離を維持。新サービス不要 |
| `web_impl/sub_agent_jobs.py`, `command_policy.py` | uag-web。Webの通知・確認とコマンド許可境界 |
| `static/` | uag-webのみでビルド・wheelへ同梱 |
| `templates/index.html` | 現状Jinja設定はあるがページルートはSPAを配信。参照と代替動作を検証して移行 |
| `tests/test_web*.py`, `test_memory_v3_web_api.py`等 | uag-webに移行。共通認証/Sandbox/Sessionのテストは本体に残す |
| CLI / GUI / A2A / Provider / Tools / MCP / Skills | 本体に残す |
| `runtime/`, `auth/`, Memory/Session/Sandbox/OTel | 本体に残し、Webからライブラリとして利用 |

ファイルの配置変更だけでは不十分。現在のWebホストは`core`のプロセス共通状態、
`util_tools`、Session選択コンテキスト、実行ライフサイクル、認証再検証、
Sandbox broker、OTelのtrusted ingressとtrace所有権に依存する。
これらをWebへコピーすると権限や実行スコープが分岐するため禁止する。

## 共通APIと逆依存

本体からWeb実装を直接importしている箇所は次の2つ。

1. `tools/__init__.py`のツール説明表示 → `web_impl.rooms`。
1. `runtime/sub_agent_job_access.py`のWeb Job解決 → `web_impl.sub_agent_jobs`。

最初のPRでは既存の`ToolCallbacks`に`tool_trace(name, content)`を追加し、
Webが現在のルームへの配信関数を設定する。呼び出し前のマスクと長さ制限を維持し、
生ツール結果を渡さない。配信先がない場合は他ルームや標準出力へ流さない。

Jobについては`register_web_job_runtime_resolver(resolver)`でWeb側から解決関数を
登録する。本体の認証済み・foreground限定チェックと、Webのroom/session照合を
両方維持する。リゾルバー不在・例外は利用不可として扱う。
CLI/GUI/A2Aの既存経路には変更を加えない。

Web側の`core`依存全体を巨大なfacadeで包み直すことはしない。
既存の共通APIを再利用し、必要な箇所だけ公開面を整える。
`routes_observability.py`の`trace_ownership_runtime._runtime_state`参照は
独立版公開までに公開の読み取りAPIへ置き換える候補。所有権検証やepochの再検証は維持する。

## 通信互換性

HTTPの全ルートはインベントリに列挙した。OpenAPIの比較に加え、
非公開integrationルート、WebSocket、静的配信を比較する。

接続は同一オリジンの`/ws?room=<room_id>&lang=<language>`。
room省略、Origin不許可、認証/room許可失敗は1008で閉じる。
`lang`の既存許容値はja/en/ar。UI側の翻訳辞書はそのまま移す。
接続時だけでなく受信メッセージごとに認証設定とroomアクセスを再検証する。
ユーザーやprojectのIDをクライアント入力から信頼する方式へ変更しない。

| クライアント → サーバー type | 内容 |
| --- | --- |
| `user_input` | `text`, `attachments`, `client_message_id`。既存のサーバー側添付検証と実行を使用 |
| `command` | `text`。既存のremote許可リストとセッションコマンドガードを使用 |
| `set_modes` | `reasoning`, `verbosity`。既存の許可・適用処理を維持 |
| `interrupt` | そのroomが所有するforegroundのみ中断。確認待ちも解除 |
| `human_ask_response` | `text`, `is_password`。サーバーで記録した質問元principalと照合 |

サーバー → クライアントは次の既存JSONイベントを維持する。

- `init`: messages / input_history / status / modes / private_session / project_id / authn_kind等。
- `message`: `message`。client_message_idによりローカルechoを置換する。
- `status`: `status`、`tool_activity`: `name`、`modes`: `modes`。
- `assistant_stream_start`: `id`、`assistant_stream_delta`: `id, delta`、
  `assistant_stream_replace`: `id, content`、`assistant_stream_end`または
  `assistant_stream_interrupted`: `id`。
- `reasoning`: `content`、`log`: `content`/`content_html`。
- `human_ask`: 既存のmessage/passwordフラグとjob識別情報。
  `human_ask_cancelled`, `job_snapshot`, `image_event`, `lifecycle`も保持。

再接続時は履歴と実行中ストリームのスナップショットを復元する。
切断と実行キャンセルは同一ではない。古いsocketのclose/messageが新しい接続を
壊さない既存ガードを維持する。通信仕様に新しいポートは追加しない。

## 認証・実行スコープと回帰項目

| 項目 | 維持する境界 / 主な検証 |
| --- | --- |
| OIDC | Code + PKCE、state/nonce/browser binding、サーバー側token/session管理、設定変更時再検証 |
| Cookie | 既存Secure既定、HttpOnly、SameSite=lax、失効とlogout |
| Origin | WebSocketとHTTP更新の共通Origin policy。integration専用の既存例外は拡張しない |
| ユーザー/room/project | IdentityResolverとRoom/ProjectAccessPolicyを継続利用。権限剥奪と別principalを拒否 |
| human_ask | 質問元principal固定、並列job/roomの分離、interrupt/cancel時解除 |
| Session | private-room復元、ロード済みsessionへの書込、room間切替、busyガード、export/import |
| Sandbox | trusted turn scope、既存MXC capability検証、host fallback禁止、spawn子のscope/RPC検証 |
| 並列 | room worker上限、processごとのcore状態、接続/切断、private-room掃除、MemoryStore解放 |
| OTel | trusted ingress、親子span、trace所有権・アクセス権・epoch再検証、停止時flush |
| CLI/GUI/A2A | 起動import、ツールcallback、Job gate、Session/Sandbox/OTelの既存回帰 |

テスト対象はインベントリのWeb利用テスト、`frontend/tests/*.test.mjs`、
`test_sub_agent_job_hosts.py`、`test_tool_result_display.py`と共通runtime/authの回帰。
Linuxでの成功だけでWindows/macOSの検証済みとはしない。CIに3 OSの起動・
パッケージ・認証/room/workerテストを置く。実Sandbox/実OIDC/実Providerの
接続を必要とする項目は、モックテストと区別して結果を記録する。

## フロントエンドと配布

Viteは現在`src/uagent/static`へ出力する。新構成は
`src/uag_web/static`へ出力し、同梱した成果物をFastAPIが配信する。
既存の`socket-lifecycle.test.mjs`も本体の成果物パスを参照するので修正する。
開発proxyには`/auth`と`/static`も含め、OIDCのredirect URI/Origin設定を
同一オリジン運用と整合させる。既存のOrigin検証を弱めて通さない。

`frontend/index.html`はTailwind CDNとGoogle Fontsに依存し、PreviewPanelは
プレビューHTMLへTailwind CDNを注入する。通常UI用のTailwindとfontを
ビルド依存へ移す候補とし、CSS差分・日本語/RTL/モバイルを検証する。
プレビューHTMLは通常UIとは別の外部コンテンツ境界として調査する。
CDNの存在を隠してオフライン対応済みとは報告しない。

Python名は`uag-web`、モジュールは`uag_web`、entry pointは
`uagw = uag_web.server:main`。依存に互換APIを含む`uag[core,web]`と
FastAPI/uvicorn等のWeb実行依存を明記する。利用者による本体の手動導入は不要。
未リリースのAPIを使う間はローカルeditableの両パッケージで検証し、
公開前に本体のAPI導入バージョンを下限に設定する。

本体の`uagw` entry pointとWebのentry pointを恒久的に共存させない。
本体から旧entry pointを除くリリースとWeb初回リリースを連携させる。
PyPI公開はこのPRの作成と別の操作であり、公開済みとは扱わない。

本体の`pyproject.toml` package-dataと`MANIFEST.in`からstatic/templatesを
除き、wheel/sdistを実際に開いてWebコード・UI成果物が含まれないことを確認する。
Web wheelは独立した環境にインストールし、`uagw --help`、HTTP配信、
WebSocket/認証の契約テストを行う。Web単独修正で本体wheelが変わらないことも確認する。

## PR分割とマージ順序

1. 本体: 本文書・インベントリと2か所の逆依存解消。旧Web維持、callback回帰を確認。
1. uag-web: パッケージ、Svelte、ビルド/配布CI。続いてWeb専用backendと既存テストを移行。
   1のAPIを前提とする。リポジトリ作成権限が現在の外部ブロッカー。
1. 本体: 必要最小限の共通API公開が追加で必要なら個別PR。Webとの統合検証。
1. 本体: 独立版の受け入れ成功後に旧Web/成果物/entry point/不要依存を削除。
   README、DEVELOP、起動方法、CIパスを更新。CLI/GUI/A2Aの最終回帰。
1. 両方: 分離したwheel/sdist検査、3 OS CI、英語のCodexレビュー依頼と指摘検証。
   ユーザーがマージを判断する。無許可のマージはしない。

ZEN-LipSyncはこの作業に含めない。コード・SDK・素材を同梱しない。
将来の別PRで独自ライセンスと再配布許諾を確認し、必要が明らかになる前に
アバターエンジン用の抽象化は追加しない。
