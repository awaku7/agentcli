# packet_send 設計

## 目的

Scapyによるパケット生成・送信を提供する。ネットワークに影響するWRITE操作として独立管理する。

## 対応レベル

### Level 1: 高レベル操作

- ICMP
- UDP
- TCP
- ARP

### Level 2: 構造化カスタムパケット

```json
{
  "packet_type": "custom",
  "layers": [
    {"type": "IP", "fields": {"dst": "192.168.1.10"}},
    {"type": "UDP", "fields": {"dport": 9999}},
    {"type": "Raw", "data": "test"}
  ],
  "count": 1,
  "interval": 1.0,
  "dry_run": true
}
```

Python式を直接`eval`する方式は採用しない。

## 入力

```json
{
  "packet_type": "udp",
  "destination": "192.168.1.10",
  "destination_port": 9999,
  "payload": "test",
  "count": 1,
  "interval": 1.0,
  "interface": "auto",
  "dry_run": true
}
```

## 必須安全機能

- `dry_run=true`を既定値にする
- 許可対象IP/CIDRを設定する
- 最大送信数を設定する
- 最小送信間隔を設定する
- ペイロードサイズを制限する
- ブロードキャスト、マルチキャスト、Raw IPを別扱いにする
- 送信前にパケット概要を返す
- 送信結果を監査ログへ記録する

## 推奨設定

```yaml
max_packets_per_call: 10
min_interval_ms: 100
max_payload_bytes: 1400
allow_broadcast: false
allow_raw_ip: false
```

## Python依存

```text
scapy
```
