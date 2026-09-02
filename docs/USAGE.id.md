# USAGE — Mode tertanam

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### Mode tertanam

Untuk deployment lokal dengan sumber daya terbatas, gunakan `--embedded` dan muat secara eksplisit hanya alat yang diperlukan aplikasi.
Dalam mode tertanam, `--tool-genre-mask` diabaikan; opsi `--enable-tool` yang diulang mempertahankan urutan alat yang ditentukan.

Lihat [referensi penggunaan CLI](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded).

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=100`: 連続fresh tool callの上限です。
