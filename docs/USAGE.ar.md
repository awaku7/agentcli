# USAGE — الوضع المضمّن

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### الوضع المضمّن

لعمليات النشر المحلية ذات الموارد المحدودة، استخدم `--embedded` وحمّل صراحةً الأدوات التي يتطلبها التطبيق فقط.
في الوضع المضمّن، يتم تجاهل `--tool-genre-mask`، بينما يحافظ تكرار خيارات `--enable-tool` على ترتيب الأدوات المحدد.

راجع [مرجع استخدام CLI](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded).

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=32`: 連続fresh tool callの上限です。
