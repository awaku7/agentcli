# UAG → UAG Admin：JSONファイルで簡単に連携

## OTel送信状態の確認（追加オプション不要）

UAGの会話中に `:otel` を入力すると、そのUAGプロセス自身が確認したOTelの状態を表示します。CLIとGUI、Webの共通コマンド処理を使用し、LLMを呼び出したり新しい通信を発生させたりしません。

```text
:otel
```

`OTel: ON/OFF` は有効設定、`Delivery` はローカルExporterの直近状態です。主な値は `awaiting_export`（まだ送信なし）、`sent`（Exporterが成功を返した）、`failed`（送信失敗）、`retry_cooldown`（失敗後の再試行待ち）、`no_endpoint`（送信先がない）、`dependencies_unavailable`（ライブラリ不足）です。最後の送信試行・成功・失敗日時（UTC）も確認できます。**送信成功がAdminへの保存・表示完了を保証するわけではありません。** Adminでの実受信はAdminテレメトリ画面の最終受信日時で確認してください。

状態は**稼働中のUAGプロセスのメモリ内だけ**に保持し、新しいファイル・DB・設定・追加の起動オプションは作りません。会話内容、URL、トークン、エラー本文も記録しません。A2Aでも共通Exporterは状態を把握しますが、A2Aプロトコルからの `:otel` コマンド実行は提供しません。

## CLIだけで利用する場合（UAG Webは不要）

UAG AdminのCLI専用連携対応版では、UAG Web（`uagw`）を起動せずに、通常の `uag admin export` で生成した連携JSONをAdminに取り込めます。

```powershell
uag admin export --output uag-admin-link.json
uag --otel
```

Admin管理者が「UAGインスタンス → UAG連携ファイルから登録」でJSONを取り込むと、CLIからAdminへ直接OTLPトレースが送信されます。AdminからUAG Webに接続できない場合、インスタンスは**Web未検証・状態不明**として登録されます（オンラインと偽装せず、Web機能や権限は認定されません）。Webが認証エラー（401/403など）を返した場合は登録を拒否し、未検証登録には自動で切り替わりません。連携ファイルを取り込んだら転送用JSONを削除し、UAGの保護済み資格情報は保持してください。

別PCのCLIから送る場合は、`uag admin export --admin-url https://admin.example.net --output uag-admin-link.json` のようにAdminのHTTPS URLを指定します。プロセス状態の**別PC監視**には、従来どおりSupervisorが必要です。通常のCLI送信そのものにSupervisorは不要です。

## 同じWindows PC（UAG Webも利用する場合）

UAGの通常の作業ディレクトリで実行（`.env.sec`がある場合はそのフォルダで実行）。

~~~powershell
uag admin export --output uag-admin-link.json
uagw --otel
~~~

別の場所から実行したい場合は`--workdir "C:\UAGの作業フォルダ"`を指定する。venv作成は不要。UAG/Adminの標準localhost URL（8000/8088）が使われる。

## 別PC

~~~powershell
uag admin export --workdir "C:\UAGの作業フォルダ" --uag-url https://uag.example.net --admin-url https://admin.example.net --output uag-admin-link.json
uagw --otel
~~~

出力した`uag-admin-link.json`を安全な方法でAdmin側に渡し、管理画面の**UAGインスタンス → UAG連携ファイルから登録**から取り込む。異なるホスト間の接続にはHTTPSを使う。`--uag-url`はAdminからUAGへのURL、`--admin-url`はUAGからAdminへのURL。

**注意:** JSONにはマニフェスト用とOTLP用の2種類、`--supervisor-url` 指定時はSupervisor用を加えた3種類のBearer秘密が平文で含まれる。Git/Issue/会話/公開共有へ載せず、取込後は削除する。秘密情報はUAGの状態ディレクトリに保護して保持するので、次回出力やUAG再起動でもトークン/instance UUIDは維持される。明示的な`--rotate`以外では再生成しない。UAGでOTelを使うには`--otel`等の明示的opt-inが必要。本文キャプチャはOFFのまま。

## 受信開始と復旧

Adminへ取り込む前のOTLP送信は404（未登録なら401）、Admin停止中は接続エラーになります。ペアリング先への送信は失敗後30秒間休止し、次の新しいSpanバッチで再試行します。失敗中・休止中のSpanは再送されません。取り込み完了後、30秒以上待って新しい会話を行ってください。修正前の0.7.38では最初の送信失敗後に送信が停止し続けるため、Adminの起動と取り込みが済んだ状態で `uagw --otel` を再起動してください。


## CLI / Web / GUI / A2A の共通設定

保存済みの連携設定とOTLP送信処理は共通です。同じユーザー・状態ディレクトリで起動してください。

| 起動口 | テレメトリ有効 | 明示的に無効 |
|---|---|---|
| CLI | `uag --otel` | `uag --no-otel` |
| Web | `uagw --otel` | `uagw --no-otel` |
| GUI | `uagg --otel` | `uagg --no-otel` |
| A2A | `uaga --otel` | `uaga --no-otel` |

無指定の既定はOFFです。ただし、作業フォルダーの `.env` / `.env.sec` またはプロセス環境で `UAGENT_OTEL_ENABLED=1` が設定されていれば有効になります。`--no-otel` はその設定より優先します。連携ファイルが保存されているだけでは有効になりません。無効時はOTel依存確認・exporter生成・送信を実行しません。


## 別PCのSupervisorも同じJSONから登録

別PCのSupervisorを使う場合は、UAGホストで **SupervisorのHTTPS URLを1つ指定**して連携ファイルを出します。PID・トークン・UUIDの手入力は不要です。

~~~powershell
uag admin export --uag-url https://uag.example.net --admin-url https://admin.example.net --supervisor-url https://supervisor.example.net --output uag-admin-link.json
~~~

Supervisorの認証用トークンは既存の保護済み連携資格情報ファイルに、別用途の独立したBearerとして保存します。UAG Adminは同じJSONを取り込むだけで、許可済みSupervisorの接続情報も登録します。

別PCではSupervisor（`uag-admin-supervisor`）をUAGと同じOSユーザー・同じ `UAGENT_STATE_DIR` で起動し、HTTPSリバースプロキシとAdmin側の `UAG_ADMIN_ALLOWED_SUPERVISOR_HOSTS` 許可ホスト設定を準備してください。Supervisorは既定で `127.0.0.1:8091` だけで待ち受け、保護済み `~/.uag/admin_pairing_credentials.json` 内の独立した `supervisor_bearer` を自動で読み込みます。ネットワーク通信の暗号化と管理者による接続先許可は省略できません。トークン・インスタンスID・PID・起動時刻の転記は不要です。

Supervisor連携を一度設定した後で `--rotate` を指定すると、manifest・OTLP・Supervisorの3種類のBearerをまとめて変更します。Supervisor連携がある場合は同じ `--supervisor-url` も指定し、出力JSONをAdminに再取り込みしてください。出力に失敗した場合、保存済みの資格情報は変更しません。


## プロセス監視の対象と制限

- **同じPC：** UAGのCLI・GUI・A2Aはユーザー専用の `~/.uag/process_registry` から、AdminがUUIDとOS起動時刻を照合して監視します。UAG WebのURLがLANアドレスやHTTPSホスト名でも読み取れます。Webの稼働中判定はloopback待受と認証済みmanifestを使います。Supervisorの別起動は不要です。
- **別PC：** UAGホストでSupervisorがこの登録簿を読み、AdminにはHTTPS経由で状態を返します。`targets.json`／PIDの手入力は通常不要です。
- 状態は画面を開く・更新するときに取得します。**定期監視通知とプロセス起動・停止は未実装**です。Supervisorのread bearerには書き込み権限を与えません。

詳しくは [UAGのプロセス自己登録](UAG_PROCESS_REGISTRY.md) を参照してください。
