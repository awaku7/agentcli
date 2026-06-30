# Auto-Pilot レビュワー性格付け 実装方向性

## 背景

`_run_auto_pilot_loop` のループ構造を Step B（判定）→ Step A（フォローアップ）に変更したことで、
レビュワーが評価する対象が「直前の作業結果のみ」に純化された。
これにより、レビュワーのプロンプト（性格付け）がより直接的に動作するようになった。

## 現状のレビュワープロンプト

`_build_judgment_messages()` 内（util_tools.py）:

```
You are a reviewer. Evaluate the conversation below and
determine whether the goal '<goal>' has been achieved.
Achieved    → COMPLETE
More needed → CONTINUE
Reply with COMPLETE or CONTINUE.
If CONTINUE, briefly state what is still missing.
Format: CONTINUE: <reason>
```

「reviewer」という最小限の役割指定のみ。性格付けはほぼなし。

## 実装方向性（案）

### A. モード選択方式

`:auto` に `--judge-mode` オプションを追加し、レビュワーの性格を切り替える。

```
:auto <goal> --judge-mode strict
:auto <goal> --judge-mode gentle
:auto <goal> --judge-mode balanced   # デフォルト（現行相当）
```

各モードのプロンプト例:

- **strict**: `"You are a strict QA inspector. COMPLETE only if the goal is fully and unambiguously satisfied. Partial progress → CONTINUE with specifics."`
- **gentle**: `"You are a supportive coach. If the essence of the goal is achieved, mark COMPLETE even if minor polish remains. Only CONTINUE if a fundamental part is missing."`
- **balanced**: 現行の `"You are a reviewer."` を微調整。

### B. 評価軸指定方式

ゴールの性質に応じてレビュワーに重視する軸を指示する。

```
:auto <goal> --judge-axis completeness
:auto <goal> --judge-axis quality
:auto <goal> --judge-axis iteration
```

- **completeness**: 「全項目が網羅されているか」を最優先
- **quality**: 「成果物の品質が十分か」を最優先
- **iteration**: 「最低 N 回の反復を経たか」を最優先（回数指定と組み合わせ）

### C. カスタムレビュワープロンプト

`UAGENT_AP_JUDGE_PROMPT` 環境変数で任意のプロンプトを注入。

```python
# _build_judgment_messages 内で env を参照
custom = env_get("UAGENT_AP_JUDGE_PROMPT")
system_prompt = custom or DEFAULT_JUDGE_PROMPT
```

### D. 段階評価の導入

COMPLETE/CONTINUE の2値ではなく3値化:

- **COMPLETE**: 達成 → ループ終了
- **CONTINUE (minor)**: 微調整のみ → フォローアップ後、再判定は簡略版
- **CONTINUE (major)**: 大きな不足 → 通常のフォローアップ

## 実装箇所

- `_build_judgment_messages()`: プロンプト生成ロジック（util_tools.py）
- `_ask_reviewer_judgment()`: 判定結果のパース（COMPLETE/CONTINUE のパースを拡張）
- `_handle_cmd_auto()`: `--judge-mode` 等のオプション解析
- `core.py` or 環境変数: モード保持用の状態

## 注意点

- プロンプトを強くしすぎると過学習（不要なフォローアップの増加 / 未完了なのにCOMPLETE）が起きる
- モード増加に伴う複雑性とのトレードオフ
- まずは `UAGENT_AP_JUDGE_PROMPT`（案C）が最小実装で効果検証しやすい
