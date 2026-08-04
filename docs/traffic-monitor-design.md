# traffic_monitor / threat_detect 設計

## 目的

継続的なネットワーク監視にはZeek、シグネチャベースの検知にはSuricataを利用する。

## traffic_monitor: Zeek

### 役割

- 接続ログ
- DNSログ
- HTTPログ
- TLSログ
- SSHログ
- ファイル・セッション情報

### Python連携

1. Zeekをpcapまたはインターフェースに対して実行
2. `conn.log`、`dns.log`などを生成
3. Pythonで読み取り、正規化・集計・通知

## threat_detect: Suricata

### 役割

- IDS/IPS
- ルールベース検知
- EVE JSON出力
- アラート・フローログ生成

### Python連携

1. Suricataを実行
2. `eve.json`をJSON Linesとして読む
3. アラートを共通イベント形式に変換

## 共通イベント

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "source": "suricata",
  "event_type": "alert",
  "src_ip": "192.168.1.10",
  "dst_ip": "192.168.1.20",
  "severity": 2,
  "signature": "example"
}
```

## 運用上の注意

- 長時間監視ではログローテーションを必須にする
- pcapとログの保存容量を制限する
- ルール更新を管理対象にする
- 監視対象インターフェースと権限を明示する

## Python依存

```text
Zeek本体またはSuricata本体
Python標準ライブラリ: subprocess, json
```
