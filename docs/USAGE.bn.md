# USAGE — এমবেডেড মোড

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### এমবেডেড মোড

সীমিত স্থানীয় ডিপ্লয়মেন্টের জন্য `--embedded` ব্যবহার করুন এবং অ্যাপ্লিকেশনের প্রয়োজনীয় টুলগুলোই স্পষ্টভাবে লোড করুন।
এমবেডেড মোডে `--tool-genre-mask` উপেক্ষা করা হয়; একাধিক `--enable-tool` অপশন দিলে নির্ধারিত টুলের ক্রম বজায় থাকে।

[CLI ব্যবহারের রেফারেন্স](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded) দেখুন।

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=32`: 連続fresh tool callの上限です。
