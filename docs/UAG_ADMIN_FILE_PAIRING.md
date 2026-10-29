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
