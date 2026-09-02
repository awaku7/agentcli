# USAGE — Embedded 모드

これはuagのEmbeddedモードと関連するCLIオプションのクイックリファレンスです。完全なコマンドライン仕様は[英語版USAGE](USAGE.md)を参照してください。

### Embedded 모드

제한된 로컬 배포에서는 `--embedded`를 사용하고 애플리케이션에 필요한 도구만 명시적으로 로드하세요.
Embedded 모드에서는 `--tool-genre-mask`가 무시되며, 여러 번 지정한 `--enable-tool` 옵션의 도구 순서가 유지됩니다.

[CLI 사용 참고서](https://github.com/awaku7/agentcli/blob/main/docs/USAGE.md#embedded)를 참조하세요.

## コマンド例

```bash
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Sort the items --max-rounds 10"
```

`--enable-tool`は複数回指定でき、指定順が保持されます。`--embedded`では`--tool-genre-mask`は無視されます。

## 関連環境変数

- `UAGENT_AUTO_SENTINEL=1`: reviewer用の追加LLMを使わないsentinel方式を有効化します。
- `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT=100`: 連続fresh tool callの上限です。
