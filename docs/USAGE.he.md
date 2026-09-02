# USAGE — מצב משובץ

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### מצב משובץ

לפריסות מקומיות מוגבלות, השתמשו ב־`--embedded` וטענו במפורש רק את הכלים הדרושים ליישום.
במצב משובץ, `--tool-genre-mask` מתעלם; אפשרויות `--enable-tool` חוזרות שומרות על סדר הכלים שצוין.

ראו את [מדריך השימוש ב־CLI](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded).

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=100`: 連続fresh tool callの上限です。
