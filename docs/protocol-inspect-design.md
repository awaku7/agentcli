# protocol_inspect 設計

## 目的

tsharkまたはPySharkを利用し、Wireshark相当の詳細プロトコル解析を行う。

## 実装方式

- 単純な抽出: `tshark`を`subprocess`で実行
- Pythonオブジェクトとして段階的に参照: PyShark
- 出力はJSONまたはJSON Linesへ統一

## 入力

```json
{
  "pcap_path": "capture.pcap",
  "display_filter": "http.request",
  "fields": [
    "frame.time",
    "ip.src",
    "ip.dst",
    "http.request.method",
    "http.host",
    "http.request.uri"
  ],
  "limit": 1000
}
```

## 代表的なフィルター

```text
http.request
dns
tls.handshake
tcp.flags.syn == 1
ip.addr == 192.168.1.10
tcp.port == 443
```

## 使い分け

```text
大量集計             → pcap_analyze/dpkt
詳細なプロトコル解析 → protocol_inspect/tshark
```

## 安全・運用

- `display_filter`を必要に応じて許可リスト化
- pcapファイルサイズと処理時間を制限
- tsharkのパスを設定で指定可能にする
- エラー時はstderrを構造化して返す

## Python依存

```text
tshark本体
任意: pyshark
```
