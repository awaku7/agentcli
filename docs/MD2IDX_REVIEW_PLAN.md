# md2idx 改善方針

## 検査項目
- ATX見出し、Setext見出し、見出しレベル
- fenced code block（```、~~~）内の偽見出し
- indented code block、HTML heading、inline code
- preamble、section番号0、空文書、CRLF

## 実装方針
1. fenced code block状態を維持し、内部の見出しを無視する。
2. ATX/Setext/HTMLの扱いを仕様として明示する。
3. preambleをsection 0とする仕様をJSON説明と一致させる。
4. 見出しの終了範囲を次の同レベル以上の見出しで決定する。
5. BOMと改行を共通ヘルパーで正規化する。

## 回帰テスト
混在見出し、コードフェンス内の偽見出し、Setext、空文書、preamble section 0、範囲外section、CRLF/BOMを検証する。
