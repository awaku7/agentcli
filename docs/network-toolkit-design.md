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

## 現行実装とリリース方針

- `pcap_analyze`: pcapの要約、フロー、検出、impact解析を提供する安定機能
- `local_network`: 自端末のインターフェース、接続、PID・プロセス相関を提供する
- `capture_analyze`: offline pcap解析、通信分類、local_network相関を統合する
- TCP再送候補は `confirmed`、`possible`、`capture_duplicate` に分類し、confidenceを返す
- `capture_analyze`の `live_capture=true` はexperimental機能として扱う
- live captureはloopbackのみ許可し、Npcap/libpcap、権限、OS差異に依存する
- offline解析は既定機能として維持し、live captureの失敗がoffline解析に影響しないようにする

## ネットワーク関連の今後の方針

### 1. 安全性を最優先する

- 読み取り、発見、監視、送信を明確に分離する
- live captureは明示指定された場合だけ実行する
- 初期対象はloopbackとし、LANインターフェースはallowlistと人間確認を必須にする
- パケット送信、スキャン、キャプチャには時間、回数、サイズ、速度の上限を設ける
- 権限昇格やNpcap/libpcapの導入を自動で行わない
- payloadや認証情報をLLMへ返さず、メタデータ中心で処理する

### 2. Python中心、外部エンジンは限定利用とする

- 標準ライブラリ、Scapy、dpkt、psutil、httpxを優先する
- nmap、tshark、Zeek、Suricataは高度な解析が必要な場合だけadapter経由で利用する
- 外部依存がない場合は構造化エラーまたは安全な代替を返す
- Python依存、外部実行ファイル、OS権限のエラーを別コードで返す

### 3. 解析結果は断定せず段階的に評価する

- 通信分類は `normal`、`review`、`suspicious`、`unknown` とする
- `suspicious`は攻撃確定ではなく、人間による確認が必要な状態を表す
- TCP再送は `confirmed`、`possible`、`capture_duplicate` を区別する
- impact scoreは攻撃判定ではなく、調査対象の優先順位付けに使う
- 検出理由、confidence、閾値、使用したデータ範囲を結果に含める

### 4. 実装フェーズ

```text
完了:
  offline capture_analyze
  通信分類
  TCP再送分類
  loopback限定live_capture

次:
  impactランキングとプロセス相関の強化
  通信分類の閾値・誤検知評価
  loopback実環境テストの継続

将来:
  明示allowlist付きLANキャプチャ
  capture_analyzeの一括監査・レポート出力
  他端末用の明示的な端末エージェント
  Zeek/Suricata/nmap/tsharkとの高度な連携
```

### 5. リリース方針

- offline解析は通常機能としてリリースする
- `live_capture`はexperimentalとしてリリースする
- experimental機能は既定で無効にする
- OS依存やドライバー不足による失敗を正常な構造化エラーとして扱う
- 実ネットワーク向け機能を正式化する前に、loopback、loopback+Npcap、権限不足、allowlist拒否をテストする
