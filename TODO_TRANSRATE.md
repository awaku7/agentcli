# TODO_TRANSLATE

## `src/uagent/translate.py` の翻訳 provider に Gemini / Claude を追加する検討

### 背景

`src/uagent/translate.py` は現在、翻訳 provider として以下を扱っている。

- `argos`
- OpenAI 互換 provider
  - `openai`
  - `azure`
  - `openrouter`
  - `openai_compat`

一方で、Gemini / Claude は未対応になっている。

### 目的

- Gemini / Claude を翻訳 provider として使えるか検討する
- 既存の翻訳設計を壊さずに追加できるか判断する
- 追加しない場合は、その理由と仕様を明確にする

### 実装方針の候補

#### 1. provider ごとに分岐を追加する

- `cfg.provider == "gemini"` の場合に Gemini 用翻訳を実行する
- `cfg.provider == "claude"` の場合に Claude 用翻訳を実行する
- それぞれ lazy import して、未インストールでも本体は壊さない

メリット:

- 実装が素直
- エラー診断が分かりやすい
- 既存の `translate_text()` の構造を大きく崩さない

注意点:

- provider ごとに SDK が異なるため、実装が少し増える
- 認証情報や model 名の扱いを整理する必要がある

#### 2. OpenAI 互換エンドポイントに寄せる

- Gemini / Claude 側に OpenAI 互換エンドポイントがあるなら、それを使って既存の `_translate_openai_compat()` に寄せる

メリット:

- 実装を増やしにくい
- 既存コードを流用しやすい

注意点:

- いつでも使えるわけではない
- ユーザー環境への依存が大きい

### 推奨

- まずは **provider ごとの分岐追加**を検討する
- 追加コストが大きい場合は、OpenAI 互換エンドポイントでの対応に寄せる

### 実装時のポイント

- 翻訳プロンプトは共通化する
  - 「翻訳だけ返す」
  - コードブロック、URL、ファイルパスは壊さない
- lazy import にする
  - 翻訳機能以外の動作に影響を与えない
- 失敗時は元テキストを返し、診断文字列を返す
- `UAGENT_TRANSLATE_DEPNAME` の扱いを provider ごとに整理する
- 必要なら API key / base URL などの env 仕様も追加する

### 確認したいこと

- Gemini / Claude を本当に公式 SDK で実装するか
- OpenAI 互換経由に寄せるか
- そもそも翻訳 provider として追加する必要があるか
