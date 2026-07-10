# rs2idx 改善方針

## 検査項目
- mod、use、const、static、type
- struct、enum、trait、impl、fn、macro_rules!
- pub(crate)/super/self、async/unsafe/extern/const fn
- `impl Trait for Type`、generic、where句、属性
- macro本体・コメント・文字列内の偽検出

## 実装方針
1. visibility/modifier/attributeを宣言に付与する。
2. impl targetとtrait実装先を保持する。
3. genericとwhere句を含む複数行signatureを処理する。
4. macro_rules!を通常macroと区別する。
5. brace scopeでimpl内部のmethodを関連付ける。

## 回帰テスト
trait impl、generic struct、macro_rules、async/unsafe fn、属性、where句、コメント・文字列、BOM/CRLFを検証する。
