# packet_probe 設計

## 目的

Scapyを使い、限定された安全なプローブ操作を提供する。任意パケット送信の前段として使用する。

## 対応操作

- `icmp_echo`
- `arp_request`
- `tcp_syn_probe`
- `udp_probe`
- `dns_query`

## 入力例

```json
{
  "action": "tcp_syn_probe",
  "target": "192.168.1.10",
  "port": 443,
  "interface": "auto",
  "timeout": 2,
  "count": 1,
  "dry_run": true
}
```

## 出力例

```json
{
  "target": "192.168.1.10",
  "port": 443,
  "reachable": true,
  "state": "syn-ack",
  "rtt_ms": 12.4
}
```

## `packet_send`との違い

- `packet_probe`: 操作を限定し、応答を解釈する
- `packet_send`: 明示的にパケットを送るだけ、または自由度の高い送信を行う

## 安全制御

- 既定は`dry_run=true`
- 1回あたりの対象数と送信数を制限
- UDPは送信間隔を制限
- ブロードキャスト・マルチキャストは別権限にする
- 実行ログを残す

## Python依存

```text
scapy
```
