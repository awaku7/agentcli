# ts2idx 改善方針

## 検査項目
- class、interface、enum、type、namespace、function
- export/default、abstract、async、generic
- decorator、arrow function、function expression
- getter/setter、constructor、method、computed method
- JSX、template literal、regex literal、コメント、複数行宣言

## 実装方針
1. decoratorを次の宣言へ関連付ける。
2. generic arrow/function/methodの型パラメータを保持する。
3. export/defaultを宣言種別と分離して処理する。
4. class scope内のmethodだけをmemberとして登録する。
5. template literal、regex literal、JSXをコメント除去処理で壊さない。
6. 複数行signatureを結合してから検出する。

## 回帰テスト
decorator付きclass/function、generic arrow、generic method、JSX、template literal、export default、複数行宣言、BOM/CRLF、section取得を検証する。
