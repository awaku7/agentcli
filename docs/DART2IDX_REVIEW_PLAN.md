# dart2idx 改善方針

## 検査項目
- class、mixin、enum、extension、typedef
- abstract/base/sealed/interface/final、factory constructor
- getter/setter、async、sync*、extension method
- annotation、generic型、複数行宣言、トップレベル関数・変数
- import/export行とコメント・文字列内の偽検出

## 実装方針
1. Dartのmodifier列と宣言形式を個別パターン化する。
2. `extension Name on Type` と匿名extensionを区別する。
3. class/mixin/extensionのscopeへメンバーを関連付ける。
4. getter/setter/factoryを通常methodと混同しない。
5. 複数行シグネチャとジェネリクスを継続行として処理する。

## 回帰テスト
annotation付きclass、generic extension、factory、getter/setter、async method、コメント・文字列内のキーワード、UTF-8 BOM/CRLF、section取得を検証する。
