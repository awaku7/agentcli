# cs2idx 改善方針

## 対象
`src/uagent/tools/cs2idx_tool.py`

## 検査項目
- namespace、class、struct、interface、record、enum、delegate
- partial、abstract、static、sealed、readonly、file-scoped namespace
- 属性（`[Attribute]`）、XMLドキュメントコメント
- asyncメソッド、コンストラクター、デストラクター、operator overload
- ジェネリック型・制約・複数行宣言
- 文字列・コメント内キーワードの誤検出
- brace scopeによるメンバー所属

## 実装方針
1. コメント・文字列・属性を安全に除去または保持し、宣言検出を分離する。
2. namespace/type/memberのスタックをbrace深度と同期する。
3. 複数行宣言は継続行を結合してから検出する。
4. section番号と行番号は1始まりで統一する。
5. 入力は共通ヘルパーでworkdir、サイズ、BOM、文字コード、改行を処理する。

## 回帰テスト
UTF-8 BOM、CP932、CRLF、属性付きrecord、generic class、async/operator、コメント・文字列内の偽定義、section取得、範囲外sectionを検証する。

## 実装ステータス

- 第1版ギャップ対応済み（cs2idx）
- 回帰テスト: `tests/test_cs2idx_tool.py`
