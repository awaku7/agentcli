# scripts/

このディレクトリには、開発・CI補助用の小さな Python スクリプトを置きます（できるだけ依存なし）。

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
gettext `.po` の簡易QCを行い、サマリを TSV/テキストで出力します。

- 入力: `src/uagent/locales/*/LC_MESSAGES/*.po`
- 出力:
  - `outputs/i18n/po_qc_summary.tsv`
  - `outputs/i18n/{locale}_po_qc.txt`

実行:

```bat
python scripts\po_qc_summary.py
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
