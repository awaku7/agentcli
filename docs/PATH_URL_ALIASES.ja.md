# パス・URLエイリアス

長いパスやURLを、ツール引数で短く指定できます。

## パスエイリアス：`@A{0}`～`@A{9}`

`path_alias` ツールでパスエイリアスを登録、一覧表示、削除できます。エイリアスの後ろには相対パスを付けられます。

```json
{"action":"set","slot":1,"path":"C:\\work\\project"}
```

登録後は、パス引数で次のように使えます。

```json
{"filename":"@A{1}/src/main.py"}
```

`@A{0}` は特別扱いされます。明示登録されていない場合は、現在の作業ディレクトリを動的に指します。明示登録すると、そのパスで上書きされます。

保存先は `~/.uag/path_aliases.json` です。`UAGENT_PATH_ALIAS_FILE` で変更できます。

## URLエイリアス：`@B{0}`～`@B{9}`

`url_alias` ツールでHTTP(S)のベースURLを登録、一覧表示、削除できます。

```json
{"action":"set","slot":0,"url":"https://example.com/api"}
```

登録後は、URL引数で次のように使えます。

```json
{"url":"@B{0}/users?active=1"}
```

保存先は `~/.uag/url_aliases.json` です。`UAGENT_URL_ALIAS_FILE` で変更できます。

## 共通操作

```json
{"action":"list"}
{"action":"delete","slot":0}
```

`set` で既存エイリアスを置き換える場合は、`"overwrite":true` を指定します。

## 適用範囲

エイリアス展開は共通のツール実行入口で行われるため、ブラウザー操作内のネストしたパス引数にも適用されます。主な対象フィールドは `path`、`filename`、`file_path`、`paths`、`output_path`、`input_path`、`root_dir`、`pcap_path`、`zip_path`、`download_dir`、`trace_path` などです。URLでは `url`、`base_url`、`business_url`、ブラウザー操作内の `url` などが対象です。

対応する構文で始まる値だけが変換されます。通常のパス、URL、メッセージ本文は変更されません。
