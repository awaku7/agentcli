# go2idx 改善方針

## 検査項目
- package、import、const、var、type
- struct、interface、alias、generic type
- func、メソッドのreceiver、pointer receiver
- 複数行signature、匿名関数、コメント・文字列内の偽検出

## 実装方針
1. Goの宣言構文をpackage/import/type/funcに分離する。
2. `func (r *Receiver) Method` のreceiverと所属型を保持する。
3. `type Name interface/struct` と型aliasを区別する。
4. brace scopeで関数本体のローカル変数を定義として扱わない。
5. generic型・関数の角括弧を正しく処理する。

## 回帰テスト
struct/interface、alias、generic、value/pointer receiver、複数行関数、コメント・文字列、BOM/CP932、section範囲を検証する。
