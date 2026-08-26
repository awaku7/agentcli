# USAGE — Indlejret tilstand

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### Indlejret tilstand

Til begrænsede lokale installationer skal du bruge `--embedded` og eksplicit indlæse de værktøjer, som programmet har brug for.
I indlejret tilstand ignoreres `--tool-genre-mask`, mens gentagne `--enable-tool`-indstillinger bevarer den angivne rækkefølge.

Se [CLI-referencevejledningen](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded).

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=32`: 連続fresh tool callの上限です。
