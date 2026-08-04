# Network Toolkit 設計

## 目的

Pythonからネットワークの発見、プローブ、パケット送信、pcap解析、プロトコル解析を行うためのツール群を設計する。

## 構成

| ツール | 実装 | 役割 |
|---|---|---|
| `network_discover` | nmap | ホスト、ポート、サービスの発見 |
| `packet_probe` | Scapy | 限定的な疎通確認・プローブ |
| `packet_send` | Scapy | 明示的なパケット生成・送信 |
| `pcap_analyze` | dpkt | 高速なpcap解析・集計 |
| `protocol_inspect` | tshark / PyShark | Wireshark相当の詳細解析 |
| `traffic_monitor` | Zeek | 通信ログの継続的生成 |
| `threat_detect` | Suricata | IDS/IPS・シグネチャ検知 |
| `web_request` | httpx | HTTP/API通信の確認 |

## 共通方針

- 読み取り系と送信系を分離する
- 外部CLIはJSON/XML/ログ出力を介して連携する
- 各ツールの結果を共通JSON形式に変換する
- 送信・スキャンは対象、速度、回数、タイムアウトを制限する
- 送信系の初期値は `dry_run=true` とする
- 実行内容を監査ログに記録する

## 権限分類

```text
READ       pcap_analyze, protocol_inspect
DISCOVERY  network_discover, packet_probe
WRITE      packet_send
MONITOR    traffic_monitor, threat_detect
```

## 共通レスポンス

```json
{
  "ok": true,
  "tool": "packet_probe",
  "timestamp": "2026-01-01T12:00:00Z",
  "duration_ms": 120,
  "data": {},
  "warnings": [],
  "errors": []
}
```

## 推奨ディレクトリ

```text
network_toolkit/
├── adapters/
├── models/
├── tools/
├── config.yaml
└── tests/
```

## 実装優先順位

1. `network_discover`
2. `pcap_analyze`
3. `packet_probe`
4. `protocol_inspect`
5. `packet_send`
6. `traffic_monitor` / `threat_detect`
7. `web_request`
