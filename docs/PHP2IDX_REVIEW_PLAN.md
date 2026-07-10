# php2idx 改善方針

## 検査項目
- namespace、class、interface、trait、enum
- abstract/final/readonly、属性（`#[...]`）
- function、method、constructor、property、class constant
- anonymous function、複数行宣言、PHPタグ、コメント・文字列内の偽検出

## 実装方針
1. PHPタグ、namespace、type、memberを分離して検出する。
2. 属性行を次の宣言へ関連付ける。
3. trait useとtrait定義を区別する。
4. brace scopeでclass/member所属を管理する。
5. string interpolationとコメントを除外してからパターンを適用する。

## 回帰テスト
属性付きreadonly class、trait/interface/enum、namespace、constructor/property、anonymous function、複数行宣言、BOM/CRLFを検証する。
