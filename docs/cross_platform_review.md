# クロスプラットフォーム対応 コードレビュー

対象: `src/uagent/tools/` のうち、今回テスト/改修したツール + システム依存が懸念されるツール

## 凡例

- ✅ 問題なし（クロスプラットフォーム対応済み）
- ⚠️ 注意点あり（特定OSで制限があるが、クラッシュはしない）
- 🛑 問題あり（他のOSで落ちる可能性がある）

---

## cmd_exec_json_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ `os.name == "nt"` で適切に分岐 | Windows: `chcp 65001 >nul &` + `shell=True` / 他: `sh -lc` + `shell=False` |
| `python -c` 改行対応 | ✅ `shlex.split()` + `shell=False` | 全OSで同一コード。`shlex` は標準ライブラリ |
| パス区切り | ✅ `subprocess.run` に委譲 | OSの実行ファイル検索パスに依存 |
| エンコーディング | ✅ `encoding="utf-8"` 固定 | |
| **課題** | ⚠️ 非Windowsで `chcp` 不使用のため、`python -c` 以外のコマンドは `sh -lc` 経由。`sh` がない環境（一部の組み込みLinux等）ではエラー | ただし `sh` がない環境は稀 |

**総評**: ✅ 適切に対応済み

---

## pwsh_exec_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ `os.name == "nt"` でpowershell検出 | ただし分岐はプローブ用。実行時は `shutil.which` で存在確認 |
| tool_level | ✅ `-1` (無効) | 起動時自動ロードされない |
| LOAD_DISABLED_REASON | ✅ `"This tool is available on Windows only."` | |
| **課題** | ⚠️ macOS/Linux でも `pwsh` (PowerShell Core) がインストールされていれば動作可能だが、description が Windows only と読める | 実害なし |

**総評**: ✅ 適切に対応済み

---

## bash_exec_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ `os.name != "nt"` かつ `shutil.which("bash")` | |
| tool_level | ✅ `0` (有効時) / `-1` (無効時) | Windows では自動無効化 |
| LOAD_DISABLED_REASON | ✅ 設定あり | |

**総評**: ✅ 適切に対応済み

---

## apply_patch_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ なし | pure Python (difflib) のみ使用 |
| ファイルI/O | ✅ `open()` + `newline` パラメータ | 全OSで同一動作 |
| パス解決 | ✅ `ensure_within_workdir()` → `Path().resolve()` | クロスプラットフォーム |
| エンコーディング | ✅ デフォルト UTF-8、パラメータ指定可能 | |
| 改行処理 | ✅ CR / LF / CRLF すべて対応 | `_detect_newline`, `_convert_newlines` で明示的に制御 |
| **課題** | ⚠️ 特になし | |

**総評**: ✅ 問題なし

---

## diff_files_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ なし | pure Python (difflib) のみ使用 |
| ファイルI/O | ✅ `open()` + `newline` パラメータ | |
| パス解決 | ✅ `ensure_within_workdir()` | |
| **課題** | ⚠️ 特になし | |

**総評**: ✅ 問題なし

---

## replace_in_file_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ なし | pure Python |
| ファイルI/O | ✅ `open()` + `newline=""` | |
| エンコーディング | ✅ `codecs.lookup()` で事前検証 | `cp932` 等 Windows固有のエンコーディングを指定しても `LookupError` として適切にハンドリング |
| regex | ✅ `re.MULTILINE` 使用 (修正済み) | |
| バイナリ検出 | ✅ `_is_probably_binary()` / `b"\x00"` チェック | 全OSで同一ロジック |
| パス解決 | ✅ `ensure_within_workdir()` | |
| **課題** | ⚠️ 特になし | |

**総評**: ✅ 問題なし

---

## read_file_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ なし | pure Python |
| ファイルI/O | ✅ `open()` | |
| BOM処理 | ✅ 自動検出 (`_is_probably_utf8_head`) | UTF-8 BOM は除去せずそのまま読む。BOM有りのJSONは `json.loads` でエラーになるが、これは仕様範囲 |
| パス解決 | ✅ `get_path()` → `ensure_within_workdir()` | |
| **課題** | ⚠️ 特になし | |

**総評**: ✅ 問題なし

---

## safe_file_ops_extras.py

| 観点 | 評価 | 備考 |
|------|------|------|
| パス解決 | ✅ `Path().expanduser().resolve()` | 全OSで同一動作 |
| パス区切り | ✅ `Path` オブジェクトに委譲 | `..` チェックは `str(p).replace("\\", "/")` で正規化済み |
| バックアップ | ✅ `.org` / `.orgN` 拡張子 | ファイル名のみの操作 |
| **課題** | ⚠️ 特になし | |

**総評**: ✅ 問題なし

---

## safe_exec_ops.py

| 観点 | 評価 | 備考 |
|------|------|------|
| ブロックリスト | ✅ `_WIN_BLOCK` / `_POSIX_BLOCK` を分離 | 各OS向けの危険コマンドを独立して定義 |
| 確認パターン | ✅ `_CONFIRM_PATTERNS` / `_META_CONFIRM` | 全OS共通 |
| **課題** | ⚠️ 特になし | |

**総評**: ✅ 適切に対応済み

---

## ble_ops_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ `hasattr(os, "add_dll_directory")` でガード | Windows の DLL パス設定のみ実行 |
| tool_level | ✅ `1` (手動ロード) | 自動ロードされない |
| LOAD_DISABLED_REASON | ⚠️ 未設定 | ただし `tool_level: 1` のため実害なし |
| 依存ライブラリ | `bleak` / `PySide6` | いずれもクロスプラットフォーム (pip) |
| **課題** | ⚠️ `tool_level: 1` のため、`tool_catalog` のクエリにヒットしてもロードされない。ユーザーが明示的に `tool_load("ble_ops")` する必要あり | 実装自体にクロスプラットフォーム上の問題はない |

**総評**: ✅ 実装上は問題なし（ロード制御は別課題）

---

## list_windows_titles_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ 3OS対応 (`sys.platform` で分岐) | Windows: `ctypes`, Linux: `ewmh`(X11) → `hyprctl`(Hyprland) → `swaymsg`(Sway) → `qdbus`(KDE) → `gdbus`(GNOME), macOS: `Quartz` (auto-install) |
| tool_level | ✅ デフォルト0 (全環境で有効) | 自動ロードされる |
| 依存ライブラリ | `ewmh` / `pyobjc` | `_pip_auto.auto_install()` で必要時に自動インストール |
| **課題** | ✅ 特になし | 未サポート環境（Wayland, BSD等）ではエラーメッセージを返す |

**総評**: ✅ クロスプラットフォーム対応済み (2025-07-13)

---

## windows_gps_tool.py

| 観点 | 評価 | 備考 |
|------|------|------|
| OS分岐 | ✅ `sys.platform == "win32"` で判定 + `LOAD_DISABLED_REASON` 設定 | |
| LOAD_DISABLED_REASON | ✅ `"This tool requires Windows (win32 platform)."` | |
| **課題** | ⚠️ `tool_level` 未設定（デフォルト0のまま） | 自動ロードはされるが、ツール内部でガードしてエラーを返すのでクラッシュしない |

**総評**: ✅ `LOAD_DISABLED_REASON` が設定されているため、ユーザーへのフィードバックは適切

---

## まとめ

| ツール | 総評 | 改善推奨 |
|--------|------|---------|
| cmd_exec_json_tool | ✅ 対応済み | なし |
| pwsh_exec_tool | ✅ 対応済み | なし |
| bash_exec_tool | ✅ 対応済み | なし |
| apply_patch_tool | ✅ 問題なし | なし |
| diff_files_tool | ✅ 問題なし | なし |
| replace_in_file_tool | ✅ 問題なし | なし |
| read_file_tool | ✅ 問題なし | なし |
| safe_file_ops_extras | ✅ 問題なし | なし |
| safe_exec_ops | ✅ 対応済み | なし |
| ble_ops_tool | ✅ 問題なし | なし |
| list_windows_titles_tool | ⚠️ 軽微 | `tool_level` / `LOAD_DISABLED_REASON` の設定を推奨 |
| windows_gps_tool | ✅ 対応済み | なし |

**結論**: `list_windows_titles_tool.py` 以外はクロスプラットフォーム対応が適切になされています。`list_windows_titles_tool.py` もクラッシュはしないが、UX 向上のために `tool_level` と `LOAD_DISABLED_REASON` を設定することを推奨します。
