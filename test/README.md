# Test Directory

このディレクトリには、ツールのテストコードが含まれています。

## テストの実行方法

### すべてのテストを実行

```bash
cd /path/to/project
python -m unittest discover test/ -v
```

### 特定のテストを実行

```bash
python -m unittest test.test_replace_in_file_tool -v
```

### テストディレクトリ内で実行

```bash
cd test
python -m unittest test_replace_in_file_tool -v
```

## テストの構造

- `test_replace_in_file_tool.py`: replace_in_file_tool のテスト
  - literal モードのテスト（preview true/false）
  - regex モードのテスト
  - マッチなしのテスト
  - 無効モードのテスト

## 要件

- Python 3.7 以上
- 追加パッケージ不要（標準ライブラリを使用）

## 注意

- テストは `./test/` ディレクトリ内のファイルを操作します。
- テスト実行前にバックアップを作成することを推奨。