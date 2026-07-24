# swift2idx 改善方針

## 検査項目
- class、struct、enum、protocol、extension、actor
- access modifier、final、static、override、mutating、async
- init/deinit、subscript、property、case、function/method
- protocol extension、generic、複数行宣言、属性、コメント・文字列

## 実装方針
1. `actor` をtypeとして扱う。
2. protocol extensionと通常extensionを保持する。
3. generic where句と複数行signatureを処理する。
4. computed property、subscript、init/deinitを分離する。
5. Swiftの文字列補間・multiline string・コメントを安全に除外する。

## 回帰テスト
actor、protocol extension、generic type、async method、subscript、property、enum case、複数行宣言、BOM/CRLFを検証する。

## 実装ステータス

- 第1版ギャップ対応済み（swift2idx）
- 回帰テスト: `tests/test_swift2idx_tool.py`
