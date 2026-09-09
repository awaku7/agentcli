# 画像Capability連携 残作業

## 現在の達成状況

- llmcapaの`ImageCapability`をUAGから取得できる
- `generate_image`と`img2img`がモデルCapabilityの`quality_values`を参照する
- `max_outputs`に応じて生成枚数を制限する
- `xhigh` / `max`をツール仕様に追加した
- Capabilityが不明なモデルは従来互換の保守的な挙動にフォールバックする
- 画像Capability用の単体テストを追加した

## 残作業

### P1: OpenAI Image APIの機能差を反映

- [ ] `output_format`を`generate_image` / `img2img`に追加
  - `png` / `jpeg` / `webp`
  - llmcapaの`output_formats`で検証
  - 保存ファイルの拡張子とMIMEタイプを出力形式に合わせる
- [ ] `output_compression`を追加
  - JPEG/WebPのみ許可
  - 0〜100の範囲を検証
- [ ] `background`をCapabilityで検証
  - `auto` / `opaque` / `transparent`
  - 透明背景時はPNG/WebPだけを許可
- [ ] 任意サイズの検証を追加
  - `size_divisible_by`
  - アスペクト比の最小・最大
  - 最大幅・最大高さ・最大ピクセル数

### P1: ストリーミング

- [ ] `stream`引数を画像生成ツールに追加
- [ ] `partial_images`を追加
- [ ] `image_generation.partial_image`イベントを処理
- [ ] 部分画像を一時ファイルとして保存し、最終画像と区別する
- [ ] llmcapaの`supports_streaming`と`partial_images_min/max`を参照する
- [ ] ストリーミング非対応モデルにはパラメータを送信しない

### P1: Responses API画像生成

- [ ] OpenAI Responses APIの画像生成ツール経路を追加
- [ ] `ImageEndpointCapability.responses_image_tool`を参照
- [ ] 上位のResponsesモデルと画像生成モデルを分離して設定
- [ ] `responses_mainline_model_required`を検証
- [ ] `action`の`auto` / `generate` / `edit`をサポート
- [ ] `previous_response_id`を利用したマルチターン編集を追加
- [ ] 会話コンテキスト内の画像入力・出力を処理
- [ ] Image APIとResponses APIの利用経路をログ・メタデータに記録

### P1: 画像編集の拡張

- [ ] `input_fidelity`の`low` / `high`を追加
- [ ] 最大入力画像数をllmcapaから取得
- [ ] 複数画像参照に対応
- [ ] File ID、URL、Base64 Data URL入力に対応
- [ ] マスク形式と透明領域の意味をプロバイダー別に扱う
- [ ] `editing` / `inpainting`非対応モデルでは編集処理を拒否

### P2: 動的ツール仕様

現在のツール仕様は起動時に静的生成されるため、モデルCapabilityに応じた動的なenum生成を検討する。

- [ ] モデル切替時に画像ツール仕様を再構築
- [ ] `quality_values`から品質enumを生成
- [ ] `output_formats`から形式enumを生成
- [ ] `background_values`から背景enumを生成
- [ ] `max_outputs`から`n`の最大値を生成
- [ ] エンドポイントCapabilityにない引数をツールから隠す

静的スキーマを維持する場合でも、実行時検証は必須とする。

### P2: プロバイダー対応

- [ ] Google Gemini / Imagenの生成・編集Capabilityを確認
- [ ] Vertex AIのモデルIDとデプロイ名を分離
- [ ] Amazon BedrockのNova Canvas / Titan Imageを確認
- [ ] xAI Grok Imagineの生成・編集仕様を確認
- [ ] Meta MuseのResponses API経路を確認
- [ ] Z.AI、Qwen、FLUX、Seedream系の仕様を確認
- [ ] OpenRouter / Togetherなどの下位モデルCapability継承を実装
- [ ] Azure OpenAIのsource modelとdeployment nameの対応を実装

### P2: 成果物・レスポンス処理

- [ ] PNG固定の保存処理を出力形式対応に変更
- [ ] 生成画像のMIMEタイプを正しく添付
- [ ] URLレスポンスとBase64レスポンスを統一的に処理
- [ ] `usage`の画像入力・画像出力トークンをメタデータに保存
- [ ] `revised_prompt`やResponses APIの`revised_prompt`を保持
- [ ] 部分画像と最終画像のartifact登録を分離

### P2: エラーと安全性

- [ ] `image_generation_user_error`を分類
- [ ] `moderation_blocked`などのエラーコードを保持
- [ ] ユーザー修正可能なエラーを無条件リトライしない
- [ ] 未対応パラメータをAPIへ送信しない
- [ ] APIキー、組織認証、地域、レート制限はCapabilityと分離する

### P3: テストとドキュメント

- [ ] OpenAI Image APIのモック生成テスト
- [ ] OpenAI Image APIのモック編集テスト
- [ ] Responses APIのモック画像生成テスト
- [ ] ストリーミングイベントのモックテスト
- [ ] Flare / SunburstのCapability連携テスト
- [ ] Capability未登録モデルの後方互換テスト
- [ ] プロバイダー別の入力・出力形式テスト
- [ ] `DEVELOP.md` / `DEVELOP.ja.md`に画像Capability連携を追記
- [ ] ユーザー向けの画像生成設定ドキュメントを更新

## 完了条件

以下を満たした時点で、画像Capability連携を実用対応とする。

1. Image APIとResponses APIをCapabilityに基づいて選択できる
2. モデル非対応のパラメータを送信しない
3. Flare / Sunburstの品質、形式、枚数、ストリーミングを利用できる
4. 画像編集で入力画像、マスク、複数参照を扱える
5. Base64、URL、ストリーミング結果を同じartifact形式で返せる
6. 未知のモデルでは安全な後方互換動作をする
7. 実APIキーを使わないモックテストが全て通過する
8. 全体テスト、ruff、py_compileが通過する

## 注意事項

- 実際の利用可否はAPIキー、組織認証、地域、契約、レート制限に依存する
- llmcapaは静的な公式仕様を提供し、UAGは実行時の権限・エラーを処理する
- プロバイダーごとに同名パラメータの意味が異なるため、共通化しすぎない
- Image APIのストリーミングと通常のLLMストリーミングは別Capabilityとして扱う
