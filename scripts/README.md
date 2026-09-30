# scripts/

このディレクトリには、開発・CI補助用の小さな Python スクリプトを置きます。

## 一覧

### compile_locales.py

gettext の `.po` を `.mo` にコンパイルします。

- 入力: `src/uagent/locales/**/LC_MESSAGES/*.po`
- 出力: 同じ場所に `.mo` を作成

実行:

```bat
python scripts\compile_locales.py
```

### po_qc_summary.py

gettext `.po` の簡易 QC を行い、サマリを TSV / テキストで出力します。

- 入力: `src/uagent/locales/*/LC_MESSAGES/*.po`
- 出力:
  - `outputs/i18n/po_qc_summary.tsv`
  - `outputs/i18n/{locale}_po_qc.txt`

実行:

```bat
python scripts\po_qc_summary.py
```

### po_rebuild_en.py

英語ロケール `en/LC_MESSAGES/uag.po` を `uagent.pot` から再生成します。

- すべての `msgstr` を `msgid` と同じ内容にします
- 既存ファイルは上書きされます

実行:

```bat
python scripts\po_rebuild_en.py
```

### po_rebuild_non_en.py

非英語ロケールの `.po` を `uagent.pot` から再生成します。

- 既存の翻訳をできるだけ保持します
- 足りない msgid を POT に合わせて補います
- 既存ファイルはバックアップしてから更新します

実行:

```bat
python scripts\po_rebuild_non_en.py src\uagent\locales\ja\LC_MESSAGES\uag.po
```

### i18n_tools_check.py

ツール側の i18n JSON（`src/uagent/tools/*.json`）を検査します。

チェック内容:

- 各言語セクション（例: `en`, `ja`, `zh_CN`…）のキー集合が一致していること
- `{name}` のようなプレースホルダが base 言語（既定 `en`）と一致していること
- （任意）`Skill_dir` / `SkillDir` の混入を警告

実行例:

```bat
python scripts\i18n_tools_check.py --root .\src\uagent\tools
```

オプション:

- `--recursive` : サブディレクトリも走査
- `--base-lang en` : base 言語キー（既定 `en`）
- `--json` : 結果を JSON で出力
- `--warn-skill-dir` : `Skill_dir` / `SkillDir` を警告として出力
- `--strict` : 警告も終了コード 1 扱い

### foundry_local_tool_call_probe.py

UAG 本体を import せず、Foundry Local の OpenAI 互換
`/chat/completions` に直接アクセスして native tool calling を切り分けます。

3 ケースを順に実行します。

1. 単純な `get_weather` 1個だけを `tool_choice=auto` で渡す
2. UAG 相当の `tool_catalog` 1個だけを `tool_choice=auto` で渡す
3. 同じ `tool_catalog` を `tool_choice` で強制する

環境変数:

- `UAGENT_FOUNDRY_LOCAL_BASE_URL`
- `UAGENT_FOUNDRY_LOCAL_DEPNAME`
- `UAGENT_FOUNDRY_LOCAL_API_KEY`（任意）

実行:

```bat
python scripts\foundry_local_tool_call_probe.py
```

完全な JSON 応答も確認する場合:

```bat
python scripts\foundry_local_tool_call_probe.py --show-json
```

個別ケースだけを試す場合:

```bat
python scripts\foundry_local_tool_call_probe.py --case catalog-forced
```

終了コードは、全選択ケース成功で `0`、tool call が期待どおり返らなければ `1`、
設定・接続・プロトコルエラーなら `2` です。

### ollama_vision_models.py

Ollama / OpenAI 互換のモデル一覧を取得し、画像入力に対応しているかを簡易に確認します。

- 環境変数:
  - `UAGENT_OLLAMA_BASE_URL`
  - `UAGENT_OLLAMA_DEPNAME`
- 主なエンドポイント:
  - `GET /v1/models`
  - `GET /api/tags`
  - `POST /api/show`
  - `POST /api/chat`

実行:

```bat
python scripts\ollama_vision_models.py --help
```

## 補足

- できるだけ依存を増やさない方針です。
- 出力先の `outputs/i18n/` は必要に応じて再生成します。
