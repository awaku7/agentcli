# kt2idx 改善方針

## 検査項目
- class、interface、object、enum class、annotation class、data/sealed class
- companion object、constructor、init、property
- 通常関数、extension function、generic function、suspend/inline/operator/infix
- nullable型、receiver型、複数行signature、annotation

## 実装方針
1. `fun Type.name(...)` をextension functionとして検出しreceiverを保存する。
2. `<T>`、nullable型、qualified typeをsignatureとして扱う。
3. companion objectと通常objectを区別する。
4. class/object/companionのscopeへメンバーを関連付ける。
5. コメント・文字列・import/packageを定義から除外する。

## 回帰テスト
extension function、generic receiver、data/sealed class、companion、property、suspend/operator、複数行宣言、BOM/CRLFを検証する。
