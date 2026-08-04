# pcap_analyze 設計

## 目的

dpktを使ってpcapを高速・軽量に解析する。大量ファイルの集計とフィルタリングを主目的とする。

## 操作

- `summary`: 全体概要
- `packets`: パケット一覧
- `flows`: フロー集計
- `endpoints`: IP/MAC/ポート集計
- `conversations`: 通信相手別集計
- `extract`: 条件一致データの抽出
- `statistics`: サイズ・時間・プロトコル統計

## 入力

```json
{
  "pcap_path": "capture.pcap",
  "operation": "summary",
  "filter": {
    "src_ip": "",
    "dst_ip": "192.168.1.10",
    "protocol": "tcp",
    "port": 443
  },
  "limit": 1000
}
```

## 出力

```json
{
  "file": "capture.pcap",
  "packet_count": 15230,
  "protocols": {"TCP": 12000, "UDP": 2800},
  "top_conversations": []
}
```

## 方針

- ストリーム処理でファイル全体をメモリに載せない
- `limit`とファイルサイズ上限を設ける
- 解析と抽出を分離する
- TCP再構成や高レベルプロトコル解析は担当しない
- 必要な場合は`protocol_inspect`へ渡す

## Python依存

```text
dpkt
```

## 現行実装との差分

現在の実装は、当初設計より拡張されている。

- `flows`にIP/CIDR/プロトコル/ポート/サイズフィルターを適用
- `extract`で条件に合うパケットを別pcapへ保存
- `detect`に問題通信検出ルールを追加
- TCP SYN Flood判定で逆方向SYN-ACKを照合
- TCP未許可ポートで初期SYN方向を基準に判定
- Well-known/Commonサービス57ポートを内蔵
- UDP/17500等の既知ブロードキャストを除外可能
- SQLiteメタデータキャッシュを`~/.uag/cache/pcap`に保存
- `impact`で機器ごとの通信影響スコアを算出

`impact`のスコアは、通信量、パケット数、接続数、再送候補、RST、SYN、ブロードキャスト量を組み合わせたヒューリスティックであり、攻撃判定そのものではない。

## 制約と次期実装

- TCP再送はキャプチャ重複やNICオフロードの影響を受けるため、再送候補として扱う
- pcap単体から他端末のプロセス名は取得できない
- `capture_analyze`によるキャプチャから解析・プロセス相関までの一括化は次期実装
- 通信分類（normal/review/suspicious/unknown）は次期実装
