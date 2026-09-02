# USAGE — एम्बेडेड मोड

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### एम्बेडेड मोड

सीमित स्थानीय परिनियोजन के लिए `--embedded` का उपयोग करें और एप्लिकेशन के लिए आवश्यक टूल ही स्पष्ट रूप से लोड करें।
एम्बेडेड मोड में `--tool-genre-mask` को अनदेखा किया जाता है; बार-बार दिए गए `--enable-tool` विकल्प टूल का निर्धारित क्रम बनाए रखते हैं।

[CLI उपयोग संदर्भ](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded) देखें।

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=100`: 連続fresh tool callの上限です。
