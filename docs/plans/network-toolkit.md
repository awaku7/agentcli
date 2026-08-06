# Network Toolkit運用品質

- Status: in-progress
- Priority: P1
- Source: [`docs/network-toolkit.md`](../network-toolkit.md)

## 対象

- impactランキングとプロセス相関の強化
- 通信分類の閾値・誤検知評価
- loopback限定live captureの継続検証
- LAN captureのallowlist設計
- Zeek / Suricata / nmap / tshark連携
- 他端末用の明示的な端末エージェント

## 制約

- 実ネットワーク操作は明示許可・allowlist必須
- `suspicious`は攻撃確定ではなく要確認
- pcapから他端末のプロセスを推測しない
- Raw packetやpayloadをLLMへ既定返却しない

## 受け入れ条件

- offline解析とlive captureの失敗を分離する
- loopback、権限不足、allowlist拒否をテストする
- 検出結果に証拠とconfidenceを含める
