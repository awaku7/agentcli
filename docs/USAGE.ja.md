# USAGE — Embeddedモード

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### Embeddedモード

制約のあるローカル環境では、`--embedded`を使用し、アプリケーションに必要なツールだけを明示的にロードしてください。
Embeddedモードでは`--tool-genre-mask`は無視され、`--enable-tool`を複数指定した場合は指定順が保持されます。

[CLI使用リファレンス](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded)を参照してください。

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=100`: 連続fresh tool callの上限です。
