---
name: jp-postage
description: "日本郵便の郵便料金（手紙・はがき・定形外・ゆうメール・速達・書留）を検索できるスキル。2025年11月改訂版データを組み込み。"
license: Apache-2.0
metadata:
  author: uagent
  version: "2.0"
---

# JP Postage Skill

日本郵便の**最新料金データ（2025年11月改訂）** をスクリプト内に直接保持しています。
外部サイトへのアクセスは不要で、オフラインでも使えます。

## 使用方法

### 全料金一覧を表示

```bash
python skills/jp-postage/scripts/postage_lookup.py
```

### キーワード検索

```bash
python skills/jp-postage/scripts/postage_lookup.py はがき
python skills/jp-postage/scripts/postage_lookup.py 定形
python skills/jp-postage/scripts/postage_lookup.py 速達
python skills/jp-postage/scripts/postage_lookup.py ゆうメール
python skills/jp-postage/scripts/postage_lookup.py 書留
```

## 収録データ

| カテゴリ | 内容 |
|---------|------|
| 定形郵便物 | 50g以内 110円 |
| 定形外（規格内） | 50g〜1kg 140〜750円 |
| 定形外（規格外） | 50g〜4kg 260〜1,750円 |
| はがき（通常） | 85円 |
| はがき（往復） | 170円 |
| ゆうメール | 150g〜1kg 190〜380円 |
| 速達 | 250g〜4kg 300〜690円 |
| 配達時間帯指定 | 250g〜4kg 440〜920円 |
| 書留 | 簡易350円 / 一般480円〜 |

## 注意事項

- 料金は **2025年11月1日改訂** 時点のものです
- 日本郵便の公式発表による変更があった場合は手動で更新が必要です
- スクリプトは `python` のみで動作し、外部依存関係はありません
