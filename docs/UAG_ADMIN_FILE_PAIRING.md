# UAG → UAG Admin：ファイルで連携（PR #294）

## 同じWindows PC

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

**注意:** JSONにはマニフェスト用とOTLP用の2種類のBearer秘密が平文で含まれる。Git/Issue/会話/公開共有へ載せず、取込後は削除する。秘密情報はUAGの状態ディレクトリに保護して保持するので、次回出力やUAG再起動でもトークン/instance UUIDは維持される。明示的な`--rotate`以外では再生成しない。UAGでOTelを使うには`--otel`等の明示的opt-inが必要。本文キャプチャはOFFのまま。

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

別PCではSupervisorサービスをUAGと同じOSユーザーで起動し、HTTPSリバースプロキシとAdmin側の許可ホスト設定を準備してください。ネットワーク通信の暗号化と管理者による接続先許可は省略できません。トークン・インスタンスID・PID・起動時刻の転記は不要です。

Supervisor連携を一度設定した後で `--rotate` を指定すると、manifest・OTLP・Supervisorの3種類のBearerをまとめて変更します。Supervisor連携がある場合は同じ `--supervisor-url` も指定し、出力JSONをAdminに再取り込みしてください。出力に失敗した場合、保存済みの資格情報は変更しません。
