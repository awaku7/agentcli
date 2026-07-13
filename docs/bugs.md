# 発見済みバグ

## B1: CR only ファイルで preserve_line_endings が機能しない

### 発見日
2025-07-13

### 発見方法
`_explore_bugs3.py` Test 1 -- IFだけを頼りにしたエッジケース探索

### 条件
- 改行が `\r` (CR only, Mac classic style) のファイル
- `preserve_line_endings=True` を指定

### 再現手順
```python
import tempfile, os, json, sys
sys.path.insert(0, "src")
from uagent.tools.diff_files_tool import run_tool as d
from uagent.tools.apply_patch_tool import run_tool as p

d0 = tempfile.mkdtemp(dir=os.getcwd())

# CR only ファイルを作成
f1 = os.path.join(d0, "cr.txt")
with open(f1, "wb") as f:
    f.write(b"line1\rline2\rline3\r")

f2 = os.path.join(d0, "cr2.txt")
with open(f2, "wb") as f:
    f.write(b"line1\rline2_modified\rline3\r")

# diff_files (preserve_line_endings=True)
r = json.loads(d({
    "path1": f1, "path2": f2,
    "preserve_line_endings": True,
}))
patch = r["diff"]

# +++ のパスを f1 に書き換えて apply
lines = patch.splitlines(keepends=True)
fixed = []
for line in lines:
    if line.startswith("+++ "):
        fixed.append(f"+++ b/{f1}\n")
    elif line.startswith("--- "):
        fixed.append(f"--- a/{f1}\n")
    else:
        fixed.append(line)

r2 = json.loads(p({
    "patch_text": "".join(fixed),
    "dry_run": False,
    "preserve_line_endings": True,
}))

with open(f1, "rb") as f:
    print(f"result: {f.read()}")
# 期待: b"line1\rline2_modified\rline3\r"
# 実際: b"line1\nline2_modified\nline3\n"
```

### 期待動作
`preserve_line_endings=True` なので、改行コード `\r` が保持され、
出力は `b"line1\rline2_modified\rline3\r"` になるべき。

### 実際の動作
CR が LF (`\n`) に変換される。
出力: `b"line1\nline2_modified\nline3\n"`

### 原因箇所 (推定)
`apply_patch_tool.py` の以下の2箇所:

1. **`_parse_patch()`** -- `preserve_line_endings` の値を無視して常に `\r` → `\n` 変換を行う
2. **`_detect_newline()`** -- CR only (`\r`) のケースを検出できず、常に `\n` を返す

### 影響範囲
- `diff_files` + `apply_patch` のラウンドトリップで CR only ファイルの改行が壊れる
- ユーザーが `preserve_line_endings=True` を指定しても期待通り動作しない

### 対策 (2025-07-13 実施)
`apply_patch_tool.py` の以下の3箇所を修正:

1. **`_detect_newline()`** -- CR only (`\r`) を検出する条件を追加
2. **`_convert_newlines()`** -- ターゲット改行が `\r` の場合の変換処理を追加
3. **`_parse_patch()`** -- 元々無条件で `\r` → `\n` 変換していたが、これはパッチテキストの解析上の正規化でありファイル内容に影響しないため、`_detect_newline` / `_convert_newlines` の修正のみで対応

### ステータス
**対策済み** (2025-07-13)

---

## B2: old_start がファイル行数より大きくてもパッチが成功する

### 発見日
2025-07-13

### 発見方法
`_explore_bugs3.py` Test 3

### 条件
- パッチのハンクヘッダ `@@ -N +M @@` の N がファイルの実際の行数より大きい

### 再現手順
```python
d0 = tempfile.mkdtemp(dir=os.getcwd())
f = os.path.join(d0, "tiny.txt")
with open(f, "w") as fh:
    fh.write("a\nb\n")
patch = f"--- a/{f}\n+++ b/{f}\n@@ -100,2 +100,2 @@\n-a\n+b\n"
r = json.loads(p({"patch_text": patch, "dry_run": False}))
print(r["ok"])  # True -- 成功と判定される
print(r["files"][0]["hunks_applied"])  # 1
```

### 期待動作
ファイルは2行しかないので `@@ -100,2` のパッチは適用できないはず。
`hunks_applied=0` またはエラーになるべき。

### 実際の動作
fuzzy match により位置が推定され、パッチが適用される (`applied=1`)。
ファイル内容は正しく変更されるが、意図しない位置にパッチが当たる可能性がある。

### 原因 (推定)
`_find_hunk_position()` の fuzzy match が、old_start のヒントを無視して
コンテキスト行の文字列一致のみで位置を特定するため。

### 影響
軽微。実際のユースケースで old_start が大きくずれることは稀。
ただし、意図しない行にパッチが当たる可能性は否定できない。

### 対策 (2025-07-13 実施)
`apply_patch_tool.py` の以下の2箇所を修正:

1. **`_apply_hunk_to_text()`** -- `old_start` がファイル行数より大きい場合（`old_start > len(text_lines)` かつ `old_start > 0`）に早期リターンするチェックを追加
2. **`_find_hunk_position()`** -- fuzzy match の結果が `start_line` から `max(10, len(before_lines)*2)` 以上離れている位置を棄却する制約を追加

### ステータス
**対策済み** (2025-07-13)

---

## (参考) 調査済みで問題なしと判断したケース

| ケース | 結果 |
|--------|------|
| path2 と text の同時指定 | 適切なエラーメッセージ |
| context_lines に負の値 | 0 に丸められ正常動作 |
| max_diff_lines に負の値 | 0 扱い (unlimited) |
| strip に負の値 | strip=0 と同等に動作 (暗黙) |
| strip がパスより大きい | 空パスになり「パスが空です」エラー |
| 存在しないファイルに dry_run | 適切なエラーメッセージ |
| 500 ハンクのパッチ | 正常動作 |
| 空ファイルへの追加パッチ | 正常動作 |
| 相対パスでのパッチ | 正常動作 |
| 不正なハンクヘッダ | 適切なエラーメッセージ |
| パッチテキストが空 | 適切なエラーメッセージ |

---

## B3: cmd_exec_json + python -c で複数行コードが実行できない

### 発見日
2025-07-13

### 発見方法
`_explore_bugs.py` 作成前の試行錯誤中に、`python -c` に複数行コードを渡すと
出力が空になる現象を確認。原因を追求した。

### 条件
- `cmd_exec_json` ツールを使う
- `command` パラメータに `python -c "..."` 形式で複数行のコードを渡す
- コード内に実際の改行 (`\n`) が含まれている

### 再現手順
```python
# これは失敗する (複数行)
cmd_exec_json(command="python -c \"import sys
print(sys.version)\"")

# これは成功する (1行)
cmd_exec_json(command="python -c \"import sys; print(sys.version)\"")
```

### 期待動作
複数行の Python コードも正しく実行される。

### 実際の動作
`stdout=""`, `stderr=""`, `returncode=0` が返る。
コマンドは実質的に実行されていない。

### 原因
`cmd_exec_json` の内部実装:
```python
p = subprocess.run(
    f"chcp 65001 >nul & {command}",
    shell=True,
    ...
)
```
`shell=True` で cmd.exe 経由で実行されるため、コマンド文字列内の
改行が cmd.exe のコマンド区切りとして解釈される。
`python -c "import sys` までが1つのコマンドと見なされ、
引用符が閉じていないため cmd.exe が後続行を待つ状態になる。
残りの行は別コマンドとして解釈される。

### 影響
- `cmd_exec_json` を使って `python -c` で複数行コードを実行しようとすると
  必ず失敗する
- 回避策として、すべてセミコロンで1行に連結するか、
  一時ファイル（`_explore_bugs.py` など）を作成して実行する必要がある

### 対策 (2025-07-13 実施)
`cmd_exec_json_tool.py` の `_run()` 関数を修正:
- `python -c "..."` / `python3 -c "..."` を検出した場合のみ
  `shlex.split()` で分解し `shell=False` でリスト実行する
- それ以外は従来通り `shell=True` + `chcp 65001` で実行

変更点:
- `import shlex` を追加 (標準ライブラリ)
- `_run()` の Windows ブロックに `if command.startswith(...)` 分岐を追加

### ステータス
**対策済み** (2025-07-13)

---

## B4: replace_in_file regex で ^/$ が行頭/行末にマッチしない

### 発見日
2025-07-13

### 発見方法
`tests/test_replace_in_file_tricky.py` -- IFだけを頼りにしたエッジケース探索

### 条件
- `mode="regex"` でパターンに `^` / `$` アンカーを使用

### 再現手順
```python
f.write_text("aaa\\nbbb\\naaa\\n")
r = replace_in_file({
    "path": str(f), "pattern": "^aaa$", "replacement": "AAA",
    "mode": "regex", "occurrence": 0, "preview": False,
})
# 期待: 全ての "aaa" 行が "AAA" に置換される
# 実際: 1件もマッチせず
```

### 原因
`re.compile(p2)` に `re.MULTILINE` フラグが指定されていなかった。
`^` / `$` が文字列全体の先頭/末尾のみにマッチしていた。

### 対策 (2025-07-13 実施)
`re.compile(p2)` → `re.compile(p2, re.MULTILINE)` に変更。

### ステータス
**対策済み** (2025-07-13)

---

## B5: replace_in_file insert_at_line で line_no=0 がエラーになる

### 発見日
2025-07-13

### 発見方法
`tests/test_replace_in_file_tricky.py` -- IFだけを頼りにしたエッジケース探索

### 条件
- `action="insert_at_line"` で `line_no=0` を指定

### 再現手順
```python
f.write_text("a\\nb\\n")
r = replace_in_file({
    "path": str(f), "action": "insert_at_line",
    "line_no": 0, "replacement": "header\\n", "preview": False,
})
# 期待: 先頭行に "header" が挿入される
# 実際: ValueError("line_no 0 out of range")
```

### 原因
`line_no < 1 or line_no > max_line` のチェックで 0 が弾かれていた。
`line_no` のデフォルト値は 0 であり、これは「未指定＝先頭行」と解釈されるべき。

### 対策 (2025-07-13 実施)
`line_no <= 0` → `line_no = 1` に補正する処理を追加。

### ステータス
**対策済み** (2025-07-13)
