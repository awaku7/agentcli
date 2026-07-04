---
name: jp-postage
description: "日本郵便の公式サイトから郵便物（手紙・はがき・レターパック等）の最新料金をスクレイピングして表示するスキル。"
license: Apache-2.0
metadata:
  author: uagent
  version: "1.0"
---

# JP Postage Skill

日本郵便の公式サイトから手紙・はがき・レターパックの最新料金を取得します。

## 使用方法

以下のスクリプトを実行するだけで最新料金が取得できます。

```bash
python skills/jp-postage/scripts/postage_scraper.py
```

## スクリプトの説明

- `scripts/postage_scraper.py` が本体です
- Playwright で日本郵便の料金ページを開き、7つのテーブルから料金データを抽出します
- 抽出結果は Markdown 形式で標準出力に出力されます
- 依存関係: `playwright`, `beautifulsoup4`（環境にインストール済み）

## テーブル構成

| テーブル | 内容 |
|---------|------|
| Table 1 | 定形郵便物（50g以内 110円） |
| Table 2 | 定形外郵便物 規格内/規格外 |
| Table 3 | ミニレター（25g以内 85円） |
| Table 4 | レターパックライト（4kg以内 430円） |
| Table 5 | レターパックプラス（4kg以内 600円） |
| Table 6 | スマートレター（1kg以内 210円） |

## 注意事項

- 日本郵便のサイト構造が変更された場合はスクリプトの修正が必要
- ページがJSレンダリング必須のため Playwright を使用
- 取得に失敗した場合はエラーメッセージを表示して終了する
