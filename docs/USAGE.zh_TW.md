# USAGE — 嵌入式模式

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### 嵌入式模式

對於受限的本機部署，請使用`--embedded`，並只明確載入應用程式所需的工具。
在嵌入式模式下會忽略`--tool-genre-mask`；重複指定`--enable-tool`時會保留指定的工具順序。

請參閱[CLI使用參考](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded)。

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=100`: 連続fresh tool callの上限です。
