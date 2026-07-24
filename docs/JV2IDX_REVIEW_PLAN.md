# jv2idx 改善方針

## 検査項目
- package、import、class、interface、enum、record、annotation interface
- generic型、extends/implements、sealed型、nested type
- constructor、method、field、static initializer、annotation
- 複数行宣言、コメント・文字列・text block内の偽検出

## 実装方針
1. annotationと通常interfaceを区別する。
2. generic型引数とthrows句を含むsignatureを処理する。
3. class/interface/enum/recordのscopeへメンバーを関連付ける。
4. constructor名とmethod名を分離する。
5. コメント、文字列、Java text blockを除外してから正規表現を適用する。

## 回帰テスト
record、annotation、generic method、constructor、enum constant、nested class、複数行宣言、BOM/CRLF、section取得を検証する。

## 実装ステータス

- 第1版ギャップ対応済み（jv2idx）
- 回帰テスト: `tests/test_jv2idx_tool.py`
