# Network Toolkit

ネットワーク関連ツールの設計、実装方針、現行ステータスを統合した文書です。

## 1. 目的と適用範囲

Pythonから、ネットワークの発見、疎通確認、パケット送信、pcap解析、詳細プロトコル解析、監視・検知、HTTP/API確認、ローカルネットワーク情報取得を統一的に提供する。

対象は、管理下の検証環境、社内ネットワーク、または明示的に許可された対象に限定する。読み取り・発見・監視・送信を分離し、送信・スキャン・ライブキャプチャは対象、速度、回数、タイムアウト、権限を制限する。

## 2. ツール構成

| ツール | 主な実装 | 権限分類 | 役割 | 状態 |
|---|---|---|---|---|
| `local_network` | psutil / OSアダプター | READ | 自端末のIF、接続、プロセス相関 | 実装済み |
| `network_discover` | nmap / socket | DISCOVERY | ホスト、ポート、サービス発見 | 実装・設計統合 |
| `packet_probe` | Scapy / socket | DISCOVERY | 限定的な疎通確認・プローブ | 実装・設計統合 |
| `packet_send` | Scapy | WRITE | 構造化パケット送信 | 制限付き |
| `pcap_analyze` | dpkt / Scapy | READ | pcapの概要、集計、抽出、検出 | 安定機能 |
| `protocol_inspect` | tshark / PyShark | READ | 詳細プロトコル解析 | 実装・設計統合 |
| `traffic_monitor` | Zeek | MONITOR | 通信ログ生成 | 外部依存 |
| `threat_detect` | Suricata | MONITOR | シグネチャ検知 | 外部依存 |
| `web_request` | httpx | READ/NETWORK | HTTP/API確認 | 実装・設計統合 |
| `web_intercept` | mitmproxy | MONITOR/WRITE | テスト用記録・変更・再送 | 任意機能 |

## 3. 共通アーキテクチャ

```text
Tool API
  ↓ 入力検証
Policy Engine
  ↓ 対象・権限・レート制限
Adapter Layer
  ├── LocalNetworkAdapter
  ├── NmapAdapter
  ├── ScapyAdapter
  ├── DpktAdapter
  ├── TsharkAdapter
  ├── ZeekAdapter
  └── SuricataAdapter
  ↓
Normalizer
  ↓
共通レスポンス + 監査ログ
```

### 共通レスポンス

```json
{
  "ok": true,
  "request_id": "req-20260101-000001",
  "operation_id": "op-20260101-000001",
  "tool": "network_discover",
  "started_at": "2026-01-01T12:00:00Z",
  "finished_at": "2026-01-01T12:00:01Z",
  "duration_ms": 1000,
  "data": {},
  "warnings": [],
  "errors": []
}
```

入力未指定値は`null`、空配列は`[]`、不明値は推測せず`null`とする。外部入力・出力時刻はISO 8601 UTC、処理時間は`duration_ms`で返す。

### 共通エラー

```text
INVALID_INPUT
TARGET_NOT_ALLOWED
RATE_LIMIT_EXCEEDED
TOOL_NOT_FOUND
PERMISSION_DENIED
DEPENDENCY_ERROR
TIMEOUT
PARSE_ERROR
OUTPUT_LIMIT_EXCEEDED
DRY_RUN_ONLY
EXTERNAL_DEPENDENCY_MISSING
PRIVILEGE_REQUIRED
PLATFORM_UNSUPPORTED
FALLBACK_USED
```

## 4. Policy Engineと安全制御

```yaml
policy:
  allowed_targets:
    - 127.0.0.1/32
    - 192.168.1.0/24
  denied_targets:
    - 0.0.0.0/0
  max_targets_per_request: 256
  max_ports_per_request: 128
  max_packets_per_request: 10
  max_runtime_seconds: 300
  max_payload_bytes: 1400
  min_packet_interval_ms: 100
  allow_broadcast: false
  allow_multicast: false
  allow_raw_packet: false
  require_confirmation_for_write: true
```

判定順序は、入力スキーマ検証、IP/CIDR/ポート正規化、allowlist照合、権限確認、回数・サイズ・時間確認、dry-run判定、実行、結果正規化・監査記録とする。

送信・スキャン・キャプチャには時間、回数、サイズ、速度の上限を設ける。live captureは明示指定時だけ実行し、既定ではloopbackを対象とする。権限昇格やNpcap/libpcapの導入、OSパッケージの無断インストールは行わない。

## 5. `local_network`

### 5.1 目的と対応OS

OSをまたいでローカルネットワーク情報を取得する。共通情報は`psutil`、OS固有の詳細機能はアダプターで実装する。

| OS | 共通実装 | 詳細実装 |
|---|---|---|
| Linux | psutil | pyroute2 |
| Windows | psutil | PowerShell / Windows API |
| macOS | psutil | ifconfig / SystemConfiguration |

### 5.2 操作

```text
interfaces    インターフェースとアドレス
connections   TCP/UDP接続、状態、PID、プロセス名
correlate     pcapメタデータと自端末接続の照合
capabilities  OS・依存・権限の確認
```

提供情報はインターフェース名、MAC、IPv4/IPv6、ネットマスク、状態、MTU、接続状態、必要に応じた自端末プロセス情報とする。他端末のプロセス名は取得しない。

必須依存は`psutil`、Linux詳細機能は任意の`pyroute2`とする。取得不能な機能はツール全体を失敗させず、`supported=false`と警告を返す。

## 6. `network_discover`

nmapを固定引数で起動し、`-oX -`のXMLを構造化JSONへ変換する。任意コマンド文字列は受け付けない。

```text
host_discovery  -sn
port_scan       TCP/UDPポート確認
service_scan    -sV
os_scan         -O（権限・対象環境に注意）
```

対象CIDR、最大対象数、ポート数、実行時間を制限し、既定のタイミングは`T2`または`T3`とする。`-T4`以上、UDP全ポート、任意NSEスクリプトは初期設定で禁止する。nmap不在時は、定義された範囲でTCP connect等へフォールバックする。

出力にはIP、ホスト名、状態、ポート、プロトコル、状態、サービス、バージョンを含める。

## 7. `packet_probe`

任意パケット送信の前段となる限定プローブを提供する。

```text
icmp_echo
arp_request
tcp_syn_probe
udp_probe
dns_query
```

`dry_run=true`を既定値とし、対象数、送信数、UDP送信間隔を制限する。ブロードキャスト・マルチキャストは別権限とする。

TCPプローブの状態は`open`、`closed`、`filtered`、`timeout`、`unknown`に正規化する。低権限で可能なTCP connectを優先し、Raw socket等が必要な場合だけ`PRIVILEGE_REQUIRED`を返す。

`packet_probe`は操作を限定して応答を解釈し、`packet_send`は明示的な送信を行う点で区別する。

## 8. `packet_send`

ネットワークへ影響するWRITE操作として独立管理する。任意のPythonコードやScapy式を実行する機能は提供しない。

対応段階は、dry-runのみ、ICMP/UDP/TCPの限定送信、構造化レイヤー指定、特殊プロトコルの個別追加の順とする。必須制御は以下のとおり。

- `dry_run=true`を既定値にする
- 許可対象IP/CIDRを検証する
- 最大送信数、最小送信間隔、ペイロードサイズを制限する
- ブロードキャスト、マルチキャスト、Raw IPを別扱いにする
- 送信前にパケット概要を返す
- 送信結果を監査ログへ記録する

## 9. `pcap_analyze`

`dpkt`を中心にpcapを逐次処理し、必要に応じてScapyで抽出する。基本操作は以下のとおり。

```text
summary       全体概要
packets       パケット一覧
flows         フロー集計
statistics    サイズ・時間・プロトコル統計
extract       条件一致パケットを別pcapへ抽出
detect        問題通信候補を検出
impact        通信影響スコアを算出
```

IP/CIDR、プロトコル、ポート、サイズ、時間、TCPフラグ等のフィルターに対応し、`limit`、ファイルサイズ、出力先を制限する。入力と出力が同一の場合、既存ファイル上書き、パストラバーサル、破損pcap、未知リンクタイプを拒否する。

TCPペイロードの完全な再構成は担当せず、必要な詳細解析は`protocol_inspect`へ渡す。TCP再送はNICオフロード、欠落、重複の影響があるため、再送候補として扱う。pcap単体から他端末のプロセス名は取得しない。

### 検出

検出は攻撃断定ではなく、ルール、証拠、スコア、confidence、recommendationを返す。カテゴリ例は`port_scan`、`host_scan`、`connection_burst`、`beaconing`、`suspicious_dns`、`large_transfer`、`cleartext_protocol`、`repeated_failure`、`unusual_port`、`long_lived_connection`、`broadcast_anomaly`等とする。

通信分類は`normal`、`review`、`suspicious`、`unknown`とし、`suspicious`は人間による確認が必要な状態を表す。impact scoreも攻撃判定ではなく調査優先順位付けに用いる。

## 10. `protocol_inspect`

`tshark`または任意の`PyShark`で詳細プロトコル解析を行う。単純な抽出は`tshark`のJSON出力を利用し、Pythonオブジェクトとしての段階参照が必要な場合だけPySharkを追加する。

代表的なdisplay filterは`http.request`、`dns`、`tls.handshake`、`tcp.flags.syn == 1`、`ip.addr == 192.168.1.10`等。フィルター長、pcapサイズ、処理時間を制限し、stdout JSON、stderr、終了コードを検証する。

大量集計は`pcap_analyze`、詳細プロトコル解析は`protocol_inspect`に分担させる。

## 11. `traffic_monitor` / `threat_detect`

### Zeek (`traffic_monitor`)

インターフェースまたはpcapから`conn.log`、`dns.log`、`http.log`、`tls.log`等を生成し、Pythonで逐次読み取り、共通イベントへ正規化する。

### Suricata (`threat_detect`)

IDS/IPS、ルールベース検知、EVE JSONの処理を行う。`eve.json`をJSON Linesとして読み、アラートとフローイベントを分離する。

長時間監視ではログローテーション、保存容量、ルール更新、監視インターフェース、必要権限を管理対象とする。

## 12. `web_request` / `web_intercept`

### `web_request`

`httpx`でHTTPステータス、ヘッダー、API、TLS接続、JSONレスポンスを確認する。URLスキームは`http`/`https`に限定し、許可ドメイン、リダイレクト回数、レスポンスサイズを制限する。SSRF対策として内部アドレスへのアクセスを別ポリシーで管理し、Authorization、Cookie、APIキーをログに出さない。

### `web_intercept`

`mitmproxy`を任意依存として、HTTP/HTTPS通信の記録、テスト用リクエスト変更、APIデバッグ、モック・再送に利用する。Pythonアドオンで処理し、認証情報や機密ペイロードを監査ログへ記録しない。

## 13. 外部依存、preflight、フォールバック

Pythonパッケージは本体の自動インストール機構を使用し、ツールから直接`pip install`を実行しない。nmap、tshark、Zeek、Suricata、Wiresharkは外部実行ファイルとして`shutil.which()`等で検出し、不在時に無断インストールしない。

依存状態は`AVAILABLE`、`MISSING`、`WRONG_VERSION`、`NOT_EXECUTABLE`、`BROKEN`で表す。各ツールは実行前に依存、入力、権限、代替手段を確認するpreflightを持つ。

| 要求 | 第一候補 | 代替 |
|---|---|---|
| TCPポート確認 | asyncio/socket | Scapy |
| ICMP/ARP/SYN | Scapy | 権限不足なら実行不可 |
| 基本pcap解析 | dpkt/Scapy | tshark |
| 詳細解析 | tshark | 専用Pythonパーサーまたは基本情報 |
| サービス検出 | nmap | TCP接続 + バナー取得 |
| ローカルIF情報 | psutil | 標準socket情報 |
| Linux詳細情報 | pyroute2 | psutil基本情報 |

フォールバック時は`degraded=true`、使用バックエンド、要求バックエンド、`FALLBACK_USED`警告を返す。

## 14. 権限と人間確認

比較的低権限で可能な操作は、pcap読取、TCP connect、HTTP/API、psutil基本情報、DNS問い合わせ。Raw ICMP、TCP SYN、ARP、L2送信、ライブキャプチャ、低レベルNetlinkは特権が必要になる可能性がある。

`human_ask`は意思確認だけに使用し、OS権限を付与しない。特権処理が必要な場合は、固定された専用ヘルパーに構造化JSONだけを渡し、ヘルパー側でもPolicyを再検証する。

- `human_ask`でsudoパスワードを取得しない
- ユーザー確認なしにUAC/sudoを起動しない
- 任意コマンドや任意Pythonコードを昇格しない
- uag本体全体を無条件に昇格しない
- UACや権限確認を拒否された場合、同じ操作を無断再試行しない

## 15. LLMへ返すデータの最小化

処理はローカルで完結させ、LLMへは要約・件数・状態・証拠だけを返す。pcap本体、Raw packet、payload、HTTP本文、Cookie、Authorization、絶対パス、資格情報は既定で返さない。

詳細は段階取得とする。

```text
Level 0  件数・状態・統計
Level 1  通信相手・ポート・プロトコル
Level 2  パケットヘッダーの限定フィールド
Level 3  指定パケットのRaw/payload（明示指定必須）
```

既定の上限は`max_response_bytes=32 KiB`、`max_items=100`、`max_payload_bytes=0`、`max_raw_packets=0`とする。上限超過時は`truncated=true`と件数を返す。大きな結果はローカル成果物として保存し、LLMにはartifact ID、概要、件数、ハッシュだけを返す。

## 16. 監査ログ

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "request_id": "req-001",
  "tool": "packet_send",
  "action": "udp",
  "target": "192.168.1.10",
  "dry_run": false,
  "result": "sent",
  "count": 1,
  "actor": "agent",
  "error_code": null
}
```

APIキー、パスワード、Cookie、Authorization、TLS秘密情報、不要なペイロードは記録しない。

## 17. 依存関係

```text
必須・共通: psutil
Python任意: scapy, dpkt, httpx, dnspython, pyroute2, pyshark, mitmproxy
外部実行ファイル: nmap, tshark, zeek, suricata
```

## 18. テスト方針

実ネットワークへの送信を単体テストで行わず、依存、権限、外部コマンド、送信処理を分離する。

- IP/CIDR/ポート、回数、サイズ、allowlistの入力検証
- Policy判定と共通レスポンスの検証
- dry-runで実送信されないこと
- nmap XML、tshark JSON、Zeek/Suricataログの変換
- pcap fixtureの逐次解析、破損・空ファイル処理
- 外部コマンド不在、タイムアウト、権限不足、フォールバック
- payload、Cookie、Authorization、絶対パスが返らないこと
- loopback限定の統合テスト
- I18Nキー・プレースホルダー検証

実ネットワークテストは明示的に許可された専用環境でのみ実行し、通常CIでは外部ネットワークへ到達させない。

## 19. 実装ステータス

### 実装済み・安定

- `pcap_analyze`: summary/statistics/flows/packets/extract/detect/impact
- `capture_analyze`: offline pcap解析、通信分類、impact、local_network相関
- TCP再送候補分類、SYN Flood判定、未許可ポート判定
- 既知サービス・ブロードキャストの除外
- SQLiteメタデータキャッシュ
- `local_network`: interfaces/connections/correlate
- Zeek/Suricata/TShark/Nmapの検出とフォールバック
- 38言語I18Nと本体の依存関係自動インストール

### 制約

- pcapだけでは他端末のプロセス名を取得できない
- TCP再送は「再送候補」として扱う
- 外部CLIは本体から無断インストールしない
- 特権昇格は操作単位で明示同意を要求する

### 今後の実装

実装予定は [`plans/network-toolkit.md`](plans/network-toolkit.md) で管理する。

## 20. 旧設計書からの統合

この文書は、以下の旧設計書を統合したものです。以後、ネットワークツール群の設計・実装状況は本書を正とします。

- `local-network-design.md`
- `network-discover-design.md`
- `network-python-library-research.md`
- `network-toolkit-design.md`
- `network-toolkit-detailed-design.md`
- `packet-probe-design.md`
- `packet-send-design.md`
- `pcap-analyze-design.md`
- `protocol-inspect-design.md`
- `traffic-monitor-design.md`
- `web-request-design.md`

## 21. 統合前資料の詳細記録

上記の正規化された章で設計の正本を示しつつ、統合時の情報欠落を防ぐため、旧ファイルにのみ存在した詳細記述を以下に保持する。新規の設計変更は本章ではなく前章へ反映する。

<details>
<summary>docs/local-network-design.md</summary>

### local_network 設計

## 目的

OSをまたいでローカルネットワーク情報を取得する。共通情報は`psutil`、OS固有の詳細機能はOS別アダプターで実装する。

## 対応OS

| OS | 共通実装 | 詳細実装 |
|---|---|---|
| Linux | psutil | pyroute2 |
| Windows | psutil | PowerShell / Windows API |
| macOS | psutil | ifconfig / SystemConfiguration |

## 共通API

```python
class NetworkAdapter:
    def list_interfaces(self):
        raise NotImplementedError

    def list_addresses(self):
        raise NotImplementedError

    def list_routes(self):
        raise NotImplementedError

    def list_neighbors(self):
        raise NotImplementedError
```

## 共通で提供する機能

- インターフェース名
- MACアドレス
- IPv4/IPv6アドレス
- ネットマスク
- インターフェース状態
- MTU

## 入力

```json
{
  "operation": "interfaces",
  "interface": null,
  "include_down": false,
  "include_virtual": true
}
```

## operation

```text
interfaces    インターフェース一覧
addresses     IPアドレス一覧
routes        ルーティング情報
neighbors     ARP/近隣テーブル
capabilities  OS・依存・権限の確認
```

## 出力例

```json
{
  "os": "Linux",
  "interfaces": [
    {
      "name": "eth0",
      "is_up": true,
      "mtu": 1500,
      "mac": "00:11:22:33:44:55",
      "addresses": [
        {
          "family": "ipv4",
          "address": "192.168.1.20",
          "netmask": "255.255.255.0",
          "broadcast": "192.168.1.255"
        }
      ]
    }
  ],
  "warnings": []
}
```

## 実装方針

### psutil

インターフェースとアドレスの共通取得に使用する。

```python
import psutil

interfaces = psutil.net_if_addrs()
statuses = psutil.net_if_stats()
```

### Linux

ルート、近隣テーブル、Netlink、ネットワーク名前空間などLinux固有機能が必要な場合だけ`pyroute2`を使用する。

### Windows

標準機能はPowerShellまたはWindows APIアダプターで実装する。外部コマンドを使う場合も、コマンド文字列を直接受け取らず、内部で固定した引数を組み立てる。

### macOS

基本情報はpsutil、詳細情報は`ifconfig`またはmacOSのSystemConfiguration系APIを使用する。

## 依存方針

```text
必須: psutil
任意: pyroute2（Linuxのみ）
任意: Windows API / PowerShell
任意: macOS SystemConfiguration
```

## エラー・未対応の扱い

OSによって取得できない情報は、ツール全体を失敗させず、次の形式で返す。

```json
{
  "operation": "routes",
  "supported": false,
  "data": null,
  "warnings": [
    {
      "code": "PLATFORM_FEATURE_UNAVAILABLE",
      "message": "Detailed route information is not available on this platform adapter."
    }
  ]
}
```

## テスト

- Linux、Windows、macOSでインターフェース一覧を取得
- down状態・仮想インターフェースの扱い
- IPv4/IPv6の混在
- 権限不足時の警告
- pyroute2未インストール時のフォールバック
- 外部コマンドのパスや引数を固定できていること

## 現行実装

`local_network`は次の操作に対応する。

- `interfaces`: ローカルインターフェースとアドレス
- `connections`: psutilによるTCP/UDP接続一覧、状態、PID、プロセス名
- `correlate`: pcapのメタデータ検出結果と現在の自端末接続を照合

他端末のプロセス名は取得しない。pcap、IP/MAC、DNS、ホスト名などのネットワークメタデータと、自端末のプロセス情報を分離して扱う。

</details>

<details>
<summary>docs/network-discover-design.md</summary>

### network_discover 設計

## 目的

nmapをPythonから実行し、ホスト、ポート、サービス情報を構造化JSONで返す。

## 実装方式

- `subprocess`でnmapを起動
- `-oX -`でXMLを標準出力へ出力
- PythonのXMLパーサーで共通形式へ変換
- 任意のコマンド文字列は受け付けない

## 入力

```json
{
  "target": "192.168.1.0/24",
  "mode": "host_discovery",
  "ports": [],
  "timing": "T2",
  "service_detection": false,
  "os_detection": false,
  "dry_run": true
}
```

## mode

- `host_discovery`: `-sn`
- `port_scan`: TCP/UDPポート確認
- `service_scan`: `-sV`
- `os_scan`: `-O`。権限と対象環境に注意

## 出力

```json
{
  "hosts": [
    {
      "ip": "192.168.1.10",
      "hostname": "server01",
      "status": "up",
      "ports": [
        {
          "port": 443,
          "protocol": "tcp",
          "state": "open",
          "service": "https",
          "version": ""
        }
      ]
    }
  ]
}
```

## 安全制御

- 許可対象CIDRのみ実行可能
- 最大対象数、最大ポート数、実行時間を制限
- `timing`の既定値は`T2`または`T3`
- スクリプト実行は明示的な許可制
- 実行コマンドと結果を監査ログに記録

## Python依存

```text
nmap本体
Python標準ライブラリ: subprocess, xml.etree.ElementTree
```

</details>

<details>
<summary>docs/network-python-library-research.md</summary>

### Pythonライブラリ中心の実装調査

## 結論

完全にPythonライブラリだけで、nmap・Wireshark・Zeek・Suricataをすべて置き換えることは現実的ではない。

ただし、今回のツール群では次の範囲まで外部CLIを減らせる。

```text
Pythonライブラリで実装:
  TCP connect probe
  TCP/UDP通信
  ICMP/ARP/TCP特殊パケット
  pcap読み取り
  pcapの基本集計
  HTTP/API通信
  Linuxのインターフェース・ルート情報

外部エンジンを残す:
  nmapのサービス・OS検出
  Wiresharkの広範なプロトコルディセクタ
  Zeekの長時間トラフィック解析
  SuricataのIDSルールエンジン
```

## 推奨するPython中心構成

| 論理ツール | 推奨実装 | 外部依存 |
|---|---|---|
| `network_discover` | Python `asyncio` + `socket`、必要時のみnmap | nmapはオプション |
| `packet_probe` | Scapy | Npcap/libpcap等はOS依存 |
| `packet_send` | Scapy | Npcap/libpcap等はOS依存 |
| `pcap_analyze` | dpkt | なし。pcap読取のみならPythonで完結 |
| `live_capture` | Scapyまたはpcapy-ng/python-libpcap | libpcap/Npcap |
| `protocol_inspect` | PySharkまたはtshark | tshark |
| `traffic_monitor` | ZeekログのPython処理 | Zeek |
| `threat_detect` | Suricata EVE JSONのPython処理 | Suricata |
| `web_request` | httpx | なし |
| `local_network` | pyroute2 | Linux中心 |

## 1. 発見・ポート確認

### 第一候補: Python標準ライブラリ

単純なTCPポート確認なら、nmapを呼ばずに`asyncio`または`socket`で実装できる。

```python
import asyncio

async def check_port(host: str, port: int, timeout: float = 2.0):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return {"port": port, "state": "open"}
    except asyncio.TimeoutError:
        return {"port": port, "state": "filtered_or_timeout"}
    except ConnectionRefusedError:
        return {"port": port, "state": "closed"}
    except OSError as exc:
        return {"port": port, "state": "error", "error": str(exc)}
```

### できること

- TCP connect scan
- 非同期ポート確認
- バナー取得
- 接続タイムアウト
- 同時実行数の制御

### できないこと、弱いこと

- SYN scanなどの低レベルスキャン
- OSフィンガープリント
- nmap相当のサービス検出
- NSEスクリプト
- UDPスキャンの正確な判定
- 複雑なホスト発見

したがって、`network_discover`は以下の2層構成がよい。

```text
basic mode     asyncio/socketによるPython実装
advanced mode  nmapアダプター
```

### `python-nmap`の評価

`python-nmap`は便利だが、nmap本体をPythonで置き換えるものではなく、nmapプロセスのラッパーである。nmapがインストールされている必要がある。

そのため、基本実装の依存にはせず、`NmapAdapter`として任意依存にする。

## 2. パケット生成・送信

### 第一候補: Scapy

ScapyはPythonから直接パケットの作成、解析、送信、キャプチャを扱える。今回の`packet_probe`と`packet_send`の中心ライブラリにする。

```python
from scapy.all import IP, ICMP, sr1

reply = sr1(IP(dst="192.168.1.10") / ICMP(), timeout=2, verbose=False)
```

### 注意点

- OSのRAWソケット権限が必要な場合がある
- WindowsではNpcapが必要になることがある
- L2操作とL3操作で必要権限・インターフェースが異なる
- 送信レート、対象、回数をアプリ側で制限する

### 代替候補

- `socket`: TCP/UDPの通常通信
- `asyncio`: 大量のTCP/UDP接続を非同期処理
- `pyroute2`: Linuxのネットワーク設定・Netlink操作
- `h11`/`h2`: HTTP/1.1やHTTP/2の低レベル処理が必要な場合

## 3. pcap読み取り・キャプチャ

### オフライン解析: dpkt

pcapを読み、Ethernet/IP/TCP/UDPなどの基本ヘッダーを高速に処理する用途ではdpktを採用する。

```text
dpkt:
  pcap読み取り、基本プロトコル、集計に強い
  外部CLI不要
  高度なプロトコル解釈は自前実装
```

### ライブキャプチャ: Scapy

少量のライブキャプチャやプローブ確認はScapyの`sniff()`で実装する。

### ライブキャプチャ専用: pcapy-ng / python-libpcap

libpcap/NpcapのAPIを直接利用したい場合は候補になる。

```text
pcapy-ng / python-libpcap:
  libpcap APIへのPythonバインディング
  BPFフィルターやライブキャプチャに向く
  ネイティブライブラリとOS設定が必要
```

第一版ではScapyを使い、キャプチャ性能や長時間運用が問題になった場合にpcapy-ng/python-libpcapを追加する。

## 4. 詳細プロトコル解析

### PySharkの位置付け

PySharkはPythonの純粋なパケットディセクタではなく、tsharkのラッパーである。Wiresharkのディセクタを利用できる反面、tsharkのインストールが必要になる。

```text
PyShark = Python API
TShark  = 実際の解析エンジン
```

### Python中心にする選択肢

- HTTP: `httpx`、必要に応じて`h11`
- DNS: `dnspython`
- TLS: 標準ライブラリ`ssl`、必要に応じて`tls-parser`
- DHCP、SIP、3GPP等: `scapy.contrib`または個別ライブラリ
- 独自バイナリ: `struct`、`construct`
- telecom系: `pycrate`

ただし、pcapから複数プロトコルを自動判別し、Wiresharkと同等に解析する用途ではtsharkを残す方が費用対効果が高い。

### 推奨

```text
基本フィールド抽出 → dpkt
対象プロトコル限定 → 専用Pythonライブラリ
未知・複雑・多プロトコル → tshark/PyShark
```

## 5. nmap代替の検討

### Pythonだけで実装可能な範囲

```text
- ICMP Echo
- TCP connect
- UDP送信
- DNS問い合わせ
- ARP問い合わせ（Scapy）
- TCP/UDPバナー取得
- 非同期ポート確認
```

### nmapを残すべき範囲

```text
- OS検出
- サービス・バージョン検出
- TCP/IPフィンガープリント
- NSEスクリプト
- 複数方式を組み合わせたホスト発見
```

`python-nmap`や`libnmap`は、nmap本体を不要にするものではない。nmapの結果操作をPythonで行うためのアダプターとして扱う。

## 6. masscan代替の検討

masscan相当の高速・大規模スキャンをPythonだけで実装することは推奨しない。

理由:

- OS・NIC・RAW送信の差異が大きい
- 高速送信の制御が難しい
- ネットワークへの負荷管理が難しい
- Pythonの通常ソケットではmasscanの方式を再現しにくい

必要な場合は、Pythonで対象範囲・レート・監査ログを管理し、masscanを限定的にアダプターとして呼び出す。

## 7. Zeek・Suricata代替の検討

ZeekとSuricataには、完全なPython純正代替はない。

### Zeek

Zeekは受動トラフィック解析とイベント・ログ生成のエンジンである。PythonはZeekのログを読み、正規化、集計、通知する役割にする。

### Suricata

SuricataはIDS/IPSルールエンジンである。Pythonは`eve.json`を処理する役割にする。

### Pythonだけで行う場合

小規模ならScapy + dpkt + 独自ルールで実装できるが、以下は自前実装になる。

- TCPストリーム再構成
- プロトコル状態管理
- ルールエンジン
- フラグメント処理
- パフォーマンス制御
- アラート抑制

このため、監視・検知機能は外部エンジンを残す。

## 8. HTTP/API

### 第一候補: httpx

`requests`よりも同期・非同期の両方を扱いやすく、HTTP/2にも対応できるため、今回の新規実装ではhttpxを第一候補にする。

```python
import httpx

async def fetch(url: str):
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(url)
        return response.status_code, response.headers
```

### 使い分け

```text
httpx       新規実装、同期/非同期、HTTP/2
requests    既存資産、単純な同期処理
aiohttp     非同期HTTPサーバー/クライアントを重く使う場合
```

## 9. ローカルネットワーク情報

### pyroute2

Linux環境では、インターフェース、アドレス、ルート、近隣テーブルなどをPythonから取得・操作できる。

```text
Linuxのネットワーク状態 → pyroute2
Windows/macOS            → platform adapter + 標準コマンドまたはOS API
```

クロスプラットフォームの共通APIとしては、取得できない項目を`null`にし、OS別アダプターへ分離する。

## 10. 採用判定

### Pythonライブラリを標準採用

```text
scapy
 dpkt
 httpx
 asyncio / socket
 struct
 ipaddress
 json
```

### 任意依存として採用

```text
python-nmap
pyshark
pcapy-ng
python-libpcap
pyroute2
```

### 外部エンジンとして残す

```text
nmap
 tShark
 Zeek
 Suricata
 masscan
```

## 11. 改訂後の実装方針

### `network_discover`

1. `asyncio` TCP connectを標準モードにする
1. ScapyでARP/ICMP/TCPプローブを追加する
1. nmapは`advanced`モードの任意依存にする

### `packet_probe`

- Scapyを標準採用
- TCP/UDPの単純確認はsocket/asyncioでも実装可能
- L2・特殊プローブだけScapyを使用

### `packet_send`

- 通常のTCP/UDP通信はsocket/asyncio
- Raw/L2/特殊パケットはScapy
- dry-run、allowlist、レート制限を必須化

### `pcap_analyze`

- dpktを標準採用
- ライブキャプチャはScapyで開始
- 高負荷時のみpcapy-ng/python-libpcapを検討

### `protocol_inspect`

- 基本解析はdpktと専用Pythonパーサー
- 広範囲のディセクションはtshark/PySharkへフォールバック

### `traffic_monitor` / `threat_detect`

- 初期版ではZeek/Suricataのログ取り込みに限定
- Python独自エンジンは小規模ルールに限定

## 12. 参考資料

- Scapy: https://scapy.readthedocs.io/
- Scapy: https://scapy.net/
- dpkt: https://dpkt.readthedocs.io/
- PyShark: https://pyshark-packet-analysis.readthedocs.io/
- python-nmap: https://pypi.org/project/python-nmap/
- libnmap: https://github.com/savon-noir/python-libnmap
- pcapy-ng: https://github.com/stamparm/pcapy-ng
- python-libpcap: https://python-libpcap.readthedocs.io/
- pyroute2: https://docs.pyroute2.org/
- Python asyncio streams: https://docs.python.org/3/library/asyncio-stream.html
- Zeek: https://docs.zeek.org/
- Suricata: https://docs.suricata.io/
- PyCrate: https://github.com/pycrate-org/pycrate

## 13. 本体の自動インストール機構

Pythonパッケージは、本体にある`uagent._pip_auto.install_with_status()`を使用してオンデマンドで自動インストールする。各ツールで直接`pip install`を実装しない。

```python
try:
    import psutil
except ImportError:
    from uagent._pip_auto import install_with_status

    if not install_with_status("psutil", "psutil"):
        raise RuntimeError("psutil is unavailable")
    import psutil
```

対象パッケージは次の通り。

```text
scapy      packet_probe / packet_send / live_capture
httpx      web_request
dnspython  dns_query
psutil     local_network
pyroute2   Linux固有のlocal_network機能
```

nmap、tshark、Zeek、SuricataはPythonパッケージではないため、本体のPython依存自動インストール対象にはしない。`shutil.which()`で実行ファイルを確認し、未導入時は構造化エラーとOS別の導入ヒントを返す。

## 14. メンテナンス状況を踏まえた再評価

「Pythonから使える」だけでなく、リリース、対応Pythonバージョン、Issue/PR活動、OS対応を採用条件にする。

### 採用優先度が高い

| ライブラリ | 判断 | 理由 |
|---|---|---|
| Scapy | 採用 | 継続的なリリースと活発な開発が確認でき、今回の送信・プローブの中心にできる |
| httpx | 採用 | 現行のHTTPクライアントとして継続更新され、同期・非同期の両方に対応 |
| pyroute2 | Linux限定で採用 | 継続更新されているが、Linux/Netlink依存が明確 |
| dnspython | 採用 | DNS専用ライブラリとして継続更新されている |
| Python標準ライブラリ | 最優先 | 外部メンテナンスへの依存が最小。socket、asyncio、ssl、ipaddressを利用 |

### 標準依存にしない

| ライブラリ | 判断 | 理由 |
|---|---|---|
| dpkt | 新規標準依存から除外 | PyPI上の最新リリースが古く、基本機能は安定しているが、継続メンテナンスを重視する方針には合わない |
| PyShark | 新規標準依存から除外 | PyPI上の最新リリースが2023年で、tsharkのラッパーとしての利点はあるが停滞リスクがある |
| python-nmap | 不採用 | nmap本体のラッパーであり、PyPI上の最新リリースが古い。subprocess + XMLの方が依存が少ない |
| pcapy-ng | 不採用 | ネイティブ依存、OS別wheel、更新状況の不確実性がある |
| 古いnmap代替ラッパー | 不採用 | nmap相当機能を維持できているか判断しにくい |

### 代替方針

```text
nmap制御       → python-nmapではなくsubprocess + XML
TShark制御     → PySharkではなくsubprocess + JSON/Fields
基本pcap解析   → Python標準 + Scapy、必要な範囲だけ自前パーサー
TCP/UDP確認    → asyncio + socket
DNS            → dnspython
HTTP           → httpx
```

`dpkt`は既存コードの保守や固定されたpcap集計では利用してもよいが、新規の必須依存にはしない。

## 14. 採用判定のルール

ライブラリを追加するときは、以下を満たさないものを標準依存にしない。

- PyPIまたは公式リポジトリに継続的なリリース履歴がある
- 対応Pythonバージョンが明記されている
- CI、テスト、Issue/PRなどの保守状況を確認できる
- 必要なOS向けwheelまたはビルド手順がある
- ライセンスがプロジェクト要件に適合する
- 重大な脆弱性・未解決の互換性問題がない
- 代替となる標準ライブラリや成熟した外部CLIより明確な利点がある

### 機械的な確認項目

```bash
python -m pip index versions <package>
python -m pip inspect
python -m pip audit
```

パッケージ採用時は、実際に使うPythonバージョンとOSで、インストール、import、最小サンプル、fixtureテストを実行する。

## 15. 改訂後の最終構成

```text
network_discover
  ├── Python標準: asyncio / socket / ipaddress
  └── advanced: nmap subprocess + XML

packet_probe
  ├── Python標準: socket / asyncio
  └── Scapy: ICMP / ARP / SYN / 特殊プローブ

packet_send
  ├── Python標準: TCP / UDP
  └── Scapy: Raw / L2 / 特殊パケット

pcap_analyze
  └── Scapy + 必要な範囲の自前パーサー

protocol_inspect
  ├── 専用Pythonパーサー
  └── advanced: tshark subprocess + JSON

web_request
  └── httpx

local_network
  ├── psutil（共通）
  └── pyroute2（Linux固有、任意依存）
```

この構成では、メンテナンスが停滞しているPythonラッパーを避け、成熟した外部CLIは薄いsubprocessアダプターとして利用する。

</details>

<details>
<summary>docs/network-toolkit-design.md</summary>

### Network Toolkit 設計

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
1. `pcap_analyze`
1. `packet_probe`
1. `protocol_inspect`
1. `packet_send`
1. `traffic_monitor` / `threat_detect`
1. `web_request`

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

</details>

<details>
<summary>docs/network-toolkit-detailed-design.md</summary>

### Network Toolkit 詳細設計

## 1. 目的と前提

Pythonから以下のネットワーク操作を統一的に提供する。

- ネットワーク上のホスト・ポート・サービス発見
- 限定的な疎通確認とプローブ
- テスト用パケットの生成・送信
- pcapの高速解析・集計
- Wireshark相当の詳細プロトコル解析
- Zeek/Suricataによる監視・検知
- HTTP/API通信の確認

対象は、管理下にある検証環境、社内ネットワーク、または明示的に許可された対象に限定する。

## 2. 採用コンポーネント

| 論理ツール | 実装 | 実行方式 | 初期リリース |
|---|---|---|---|
| `network_discover` | nmap | subprocess + XML | 必須 |
| `packet_probe` | Scapy | Python API | 必須 |
| `packet_send` | Scapy | Python API | 必須。ただし制限付き |
| `pcap_analyze` | dpkt | Python API | 必須 |
| `protocol_inspect` | tshark | subprocess + JSON | 必須 |
| `traffic_monitor` | Zeek | subprocess + log | 後段 |
| `threat_detect` | Suricata | subprocess + EVE JSON | 後段 |
| `web_request` | httpx | Python API | 後段 |

PySharkは、tsharkの出力だけでは扱いにくい場合の追加実装とする。最初からtsharkとPySharkを二重に標準採用しない。

## 3. 依存関係の自動インストール

このツール群は、本体にある依存関係自動インストール機構を使用する。ツール側で直接`pip install`を実装しない。

### Pythonパッケージ

外部ツールのモジュール先頭で、必要なときだけ本体のヘルパーを呼び出す。

```python
from uagent._pip_auto import install_with_status

if not install_with_status("scapy", "scapy", version_spec=">=2.6.0"):
    raise RuntimeError("scapy is unavailable")

from scapy.all import IP, ICMP
```

### 方針

- importを試す
- ImportError時だけ自動インストールする
- パッケージ名とimport名が異なる場合は両方指定する
- 最低バージョンを`version_spec`で指定する
- インストール失敗時はツールを無効化し、理由を構造化エラーで返す
- ツールごとに同じパッケージを重複インストールしない
- 本体の自動インストール機構を迂回して`subprocess pip install`を呼ばない

### 予定するPython依存

```text
scapy       packet_probe / packet_send / live_capture
httpx       web_request
dnspython   dns_query
psutil      local_network
pyroute2    Linux固有のlocal_network機能
```

### 外部実行ファイル

nmap、tshark、Zeek、SuricataはPythonパッケージではないため、Python依存と同じ自動インストール対象にはしない。`shutil.which()`等で存在を確認し、未導入時はインストール手順を含む構造化エラーを返す。

```json
{
  "code": "EXTERNAL_DEPENDENCY_MISSING",
  "message": "tshark executable was not found.",
  "dependency": "tshark",
  "install_hint": "Install Wireshark/tshark for your operating system."
}
```

## 4. アーキテクチャ

```text
Tool API
  ↓ 入力検証
Policy Engine
  ↓ 対象・権限・レート制限
Adapter Layer
  ├── NmapAdapter
  ├── ScapyAdapter
  ├── DpktAdapter
  ├── TsharkAdapter
  ├── ZeekAdapter
  └── SuricataAdapter
  ↓
Normalizer
  ↓
共通レスポンス + 監査ログ
```

## 4. ディレクトリ構成

```text
network_toolkit/
├── pyproject.toml
├── src/network_toolkit/
│   ├── __init__.py
│   ├── config.py
│   ├── errors.py
│   ├── policy.py
│   ├── audit.py
│   ├── models/
│   │   ├── common.py
│   │   ├── discovery.py
│   │   ├── packet.py
│   │   └── analysis.py
│   ├── adapters/
│   │   ├── base.py
│   │   ├── nmap.py
│   │   ├── scapy.py
│   │   ├── dpkt.py
│   │   ├── tshark.py
│   │   ├── zeek.py
│   │   └── suricata.py
│   └── tools/
│       ├── network_discover.py
│       ├── packet_probe.py
│       ├── packet_send.py
│       ├── pcap_analyze.py
│       ├── protocol_inspect.py
│       ├── traffic_monitor.py
│       ├── threat_detect.py
│       └── web_request.py
├── tests/
│   ├── fixtures/
│   ├── unit/
│   └── integration/
└── config.yaml
```

## 5. 共通入力規約

### 5.1 識別子

- `request_id`: 呼び出し単位の一意ID
- `operation_id`: 外部コマンドまたは送信処理単位のID
- `tool`: 実行ツール名
- `mode`: ツール内の操作種別

### 5.2 時間

- 外部入力・出力はISO 8601 UTC
- タイムアウトは秒単位の整数または小数
- 処理時間は`duration_ms`で返す

### 5.3 空値

- 未指定の文字列は空文字ではなく`null`
- 空の配列は`[]`
- 不明な値は推測せず`null`

## 6. 共通レスポンス

```json
{
  "ok": true,
  "request_id": "req-20260101-000001",
  "operation_id": "op-20260101-000001",
  "tool": "network_discover",
  "started_at": "2026-01-01T12:00:00Z",
  "finished_at": "2026-01-01T12:00:01Z",
  "duration_ms": 1000,
  "data": {},
  "warnings": [],
  "errors": []
}
```

### エラー形式

```json
{
  "code": "TARGET_NOT_ALLOWED",
  "message": "Target is outside the configured allowlist.",
  "retryable": false,
  "field": "target",
  "details": {}
}
```

### エラーコード

```text
INVALID_INPUT
TARGET_NOT_ALLOWED
RATE_LIMIT_EXCEEDED
TOOL_NOT_FOUND
PERMISSION_DENIED
DEPENDENCY_ERROR
TIMEOUT
PARSE_ERROR
OUTPUT_LIMIT_EXCEEDED
DRY_RUN_ONLY
```

## 7. Policy Engine

### 7.1 設定例

```yaml
policy:
  allowed_targets:
    - 127.0.0.1/32
    - 192.168.1.0/24
  denied_targets:
    - 0.0.0.0/0
  max_targets_per_request: 256
  max_ports_per_request: 128
  max_packets_per_request: 10
  max_runtime_seconds: 300
  max_payload_bytes: 1400
  min_packet_interval_ms: 100
  allow_broadcast: false
  allow_multicast: false
  allow_raw_packet: false
  require_confirmation_for_write: true
```

### 7.2 判定順序

1. JSONスキーマ検証
1. 対象IP、CIDR、ポートの正規化
1. 許可対象との照合
1. 操作権限の確認
1. 回数・サイズ・時間制限の確認
1. `dry_run`なら実行せず計画を返す
1. 外部ツールまたはScapyを実行
1. 結果を正規化して監査ログに記録

## 8. network_discover 詳細

### 入力

```json
{
  "target": "192.168.1.0/24",
  "mode": "port_scan",
  "ports": [22, 80, 443],
  "protocols": ["tcp"],
  "timing": "T2",
  "service_detection": false,
  "os_detection": false,
  "scripts": [],
  "timeout_seconds": 120,
  "dry_run": true
}
```

### 実行方針

- nmapの引数は内部で組み立てる
- XML出力を使用する
- stdout/stderrを分離する
- nmapの終了コードとXML内容の両方を検証する
- `-T4`以上、UDP全ポート、任意NSEスクリプトは初期設定で禁止

### 正規化結果

```json
{
  "hosts": [
    {
      "ip": "192.168.1.10",
      "hostnames": ["server01"],
      "status": "up",
      "ports": [
        {
          "port": 443,
          "protocol": "tcp",
          "state": "open",
          "service": "https",
          "product": null,
          "version": null
        }
      ]
    }
  ]
}
```

## 9. packet_probe 詳細

### 対応モード

```text
icmp_echo       IP/ICMPを送信し応答を確認
arp_request     同一L2セグメントのARP確認
tcp_syn_probe   TCP SYNへの応答を確認
udp_probe       UDP送信とICMP等の応答を確認
dns_query       指定DNSサーバーへの問い合わせ
```

### 入力

```json
{
  "mode": "tcp_syn_probe",
  "target": "192.168.1.10",
  "port": 443,
  "interface": null,
  "timeout_seconds": 2,
  "count": 1,
  "dry_run": true
}
```

### 結果状態

```text
open        SYN-ACK等、利用可能性を示す応答
closed      RST等、閉鎖を示す応答
filtered    応答なしまたはフィルタを示す状態
timeout     タイムアウト
unknown     解釈できない応答
```

## 10. packet_send 詳細

### 実行段階

```text
Stage 1: dry-runのみ
Stage 2: ICMP/UDP/TCPの限定送信
Stage 3: 構造化レイヤー指定
Stage 4: 特殊プロトコルを個別追加
```

任意のPythonコードやScapy式を実行する機能は提供しない。

### 入力

```json
{
  "packet_type": "udp",
  "destination": "192.168.1.10",
  "destination_port": 9999,
  "source_port": null,
  "payload": "test",
  "count": 1,
  "interval_ms": 1000,
  "interface": null,
  "dry_run": true,
  "confirmation_token": null
}
```

### dry-run出力

```json
{
  "dry_run": true,
  "would_send": 1,
  "target": "192.168.1.10:9999/udp",
  "packet_summary": "IP / UDP 192.168.1.10:9999 / Raw",
  "payload_bytes": 4,
  "policy_checks": {
    "target_allowed": true,
    "count_allowed": true,
    "payload_size_allowed": true
  }
}
```

### 実送信条件

- `dry_run=false`
- 対象がallowlist内
- policyチェック合格
- WRITE権限あり
- 必要時は確認トークンあり

## 11. pcap_analyze 詳細

### 入力

```json
{
  "pcap_path": "capture.pcap",
  "operation": "flows",
  "filter": {
    "src_ip": null,
    "dst_ip": "192.168.1.10",
    "protocol": "tcp",
    "src_port": null,
    "dst_port": 443,
    "time_start": null,
    "time_end": null
  },
  "limit": 1000
}
```

### 実装方針

- `dpkt.pcap.Reader`で逐次処理
- Ethernet、IPv4、IPv6、TCP、UDP、ICMPを初期対応
- TCPペイロードの完全な再構成は対象外
- pcap-ngなどの形式は対応可否を明示する
- 大きなファイルでは結果をページングする

## 12. protocol_inspect 詳細

### 入力

```json
{
  "pcap_path": "capture.pcap",
  "display_filter": "tls.handshake",
  "fields": ["frame.time", "ip.src", "ip.dst", "tls.handshake.type"],
  "limit": 1000,
  "timeout_seconds": 120
}
```

### 実行方式

```text
tshark -r capture.pcap -Y <filter> -T json
```

- フィルター文字列は長さ制限を設ける
- pcapパスはローカル許可ディレクトリ内に限定
- stdoutをJSONとして検証する
- stderrは利用者向けエラーと内部ログに分離する

## 13. traffic_monitor / threat_detect

### Zeek

- 入力: インターフェースまたはpcap
- 出力: `conn.log`、`dns.log`、`http.log`等
- Pythonはログをtailし、共通イベントへ変換

### Suricata

- 入力: インターフェースまたはpcap
- 出力: `eve.json`
- PythonはJSON Linesを逐次処理
- アラートとflow/eventを分離して扱う

### 共通イベント

```json
{
  "source": "suricata",
  "event_type": "alert",
  "timestamp": "2026-01-01T12:00:00Z",
  "src_ip": "192.168.1.10",
  "dst_ip": "192.168.1.20",
  "src_port": 12345,
  "dst_port": 443,
  "severity": 2,
  "message": "example alert"
}
```

## 14. web_request 詳細

### 入力

```json
{
  "url": "https://example.com/api/status",
  "method": "GET",
  "headers": {},
  "query": {},
  "body": null,
  "timeout_seconds": 5,
  "follow_redirects": false,
  "max_response_bytes": 1048576
}
```

### 安全制御

- `http`/`https`以外を拒否
- allowlistドメインを設定可能にする
- リダイレクト先も再検証する
- Authorization、Cookie、APIキーをログに出さない
- SSRF対策として内部アドレスへのアクセスを別ポリシーにする

## 15. 監査ログ

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "request_id": "req-001",
  "tool": "packet_send",
  "action": "udp",
  "target": "192.168.1.10",
  "dry_run": false,
  "result": "sent",
  "count": 1,
  "actor": "agent",
  "error_code": null
}
```

ログには以下を記録しない。

- APIキー
- パスワード
- Cookie
- Authorizationヘッダー
- TLS秘密情報
- 必要性のないパケットペイロード

## 16. テスト方針

### Unit test

- IP/CIDR/ポートの入力検証
- policy判定
- nmap XML変換
- tshark JSON変換
- Zeek/Suricataログ変換
- pcap解析の固定fixture
- dry-runで実送信されないこと

### Integration test

- localhost宛てのICMP/TCP/UDP
- テスト用pcap
- モックしたnmap/tshark実行
- 実環境でのテストは明示的なオプトイン制

### 禁止事項

- CIから無関係なネットワークへスキャンしない
- CIから外部へ任意パケットを送信しない
- 実パスワードや実APIキーをfixtureに入れない

## 17. 実装順序

### Phase 1

- 共通モデル
- policy engine
- audit logger
- `pcap_analyze`
- `network_discover`

### Phase 2

- `packet_probe`
- `protocol_inspect`
- dry-runと結果正規化

### Phase 3

- `packet_send`
- confirmation token
- 送信監査ログ

### Phase 4

- Zeek
- Suricata
- httpx
- 必要に応じてPyShark

## 18. 完了条件

- すべてのツールが共通レスポンスを返す
- 外部コマンドの終了コードとstderrを処理できる
- 許可対象外への操作を拒否できる
- 送信系がdry-runで安全に確認できる
- 送信数・サイズ・速度・時間を制限できる
- 主要な入力異常とタイムアウトをテストできる
- 監査ログから誰が何を対象に実行したか確認できる

## 19. 外部コマンド・Wireshark・権限の扱い

### 19.1 基本方針

- Pythonパッケージは本体の自動インストール機構でオンデマンド導入する
- OSの外部コマンドやWireshark/tsharkは、ツール側で勝手にインストールしない
- 実行前に依存関係と権限を`preflight`で確認する
- 不足時は代替実装へフォールバックする
- 特権昇格は自動で行わず、利用者の明示的な同意を必要とする

### 19.2 外部コマンドの検出

```python
from shutil import which

path = which("nmap")
if path is None:
    # EXTERNAL_DEPENDENCY_MISSINGを返す
    ...
```

実行ファイルの確認対象:

```text
nmap
 tshark
 zeek
 suricata
 wireshark
```

`wireshark` GUIが無くても、`tshark`が存在すればCLI解析は利用可能とする。逆に、Wireshark GUIだけが存在して`tshark`が見つからない場合は、実際のtsharkパスを設定から指定できるようにする。

### 19.3 依存関係の状態

```text
AVAILABLE       利用可能
MISSING         未導入
WRONG_VERSION   バージョン不適合
NOT_EXECUTABLE  実行権限・パスの問題
BROKEN          起動はできるが自己診断に失敗
```

### 19.4 Preflight API

すべてのネットワークツールに、実行前確認の内部処理を持たせる。

```json
{
  "tool": "protocol_inspect",
  "operation": "preflight",
  "requirements": [
    {
      "name": "tshark",
      "kind": "executable",
      "required": true,
      "status": "missing",
      "path": null
    },
    {
      "name": "capture_file",
      "kind": "input",
      "required": true,
      "status": "available",
      "path": "capture.pcap"
    }
  ],
  "capabilities": {
    "can_run": false,
    "fallbacks": ["pcap_analyze"]
  }
}
```

### 19.5 代替処理

| 要求 | 第一候補 | 代替 |
|---|---|---|
| TCPポート確認 | asyncio/socket | Scapy |
| ICMP/ARP/SYN | Scapy | 権限不足なら実行不可 |
| 基本pcap解析 | tshark | Scapy |
| HTTP/DNS/TLS詳細 | tshark | 専用Pythonパーサーまたは基本情報のみ |
| サービス検出 | nmap | TCP接続 + バナー取得 |
| ローカルIF情報 | psutil | 標準socket情報 |
| Linux詳細ネットワーク | pyroute2 | psutilによる基本情報 |

フォールバックした場合は、結果に必ず含める。

```json
{
  "ok": true,
  "degraded": true,
  "backend": "scapy",
  "requested_backend": "tshark",
  "warnings": [
    {
      "code": "FALLBACK_USED",
      "message": "tshark is unavailable; basic Scapy parsing was used."
    }
  ]
}
```

### 19.6 権限チェック

#### 権限不要または比較的低い操作

- pcapファイルの読み取り
- `asyncio`によるTCP connect
- HTTP/API通信
- `psutil`による基本情報取得
- DNS問い合わせ

#### 特権が必要になる可能性がある操作

- ICMP Raw socket
- TCP SYN送信
- ARP送信・受信
- L2パケット送信
- インターフェースへのライブキャプチャ
- 低レベルのNetlink操作

OSや実行環境により必要権限は異なるため、固定的に「管理者必須」と判定せず、事前チェックと実行時エラーの両方を処理する。

### 19.7 特権不足時の動作

特権不足の場合、次の順に処理する。

1. 低権限で可能な代替方式を試す
1. 代替できない場合は安全に中止する
1. 自動的にsudo、UAC、pkexecを起動しない
1. 必要権限、対象操作、代替手段を構造化して返す

```json
{
  "ok": false,
  "errors": [
    {
      "code": "PRIVILEGE_REQUIRED",
      "message": "Raw packet transmission requires elevated privileges.",
      "operation": "tcp_syn_probe",
      "alternatives": ["tcp_connect_probe"],
      "required_privilege": "CAP_NET_RAW or equivalent"
    }
  ]
}
```

### 19.8 特権昇格の扱い

#### Windows UAC

Windowsでは、利用者の明示的な同意を前提にUAC昇格を起動できる。これは無断・サイレントな権限昇格ではなく、WindowsのUAC確認画面を表示してユーザーが許可する方式である。

ただし、uag本体のプロセス全体を昇格するのではなく、必要な処理だけを専用ヘルパーへ分離する。

```text
通常のuagプロセス
  ↓ IPC / 一時JSON / 標準入出力
UACで昇格したnetwork helper
  ↓
ScapyのRaw送信、Npcap操作、特権が必要な処理
```

#### UAC昇格の条件

- 入力に`allow_elevation=true`が明示されている
- 操作が許可対象である
- 対象IP/CIDRがallowlist内である
- 送信数、サイズ、レート制限を通過している
- UAC確認を利用者が承認する
- 実行内容を監査ログへ記録する

#### 入力例

```json
{
  "operation": "tcp_syn_probe",
  "target": "192.168.1.10",
  "port": 443,
  "allow_elevation": true,
  "dry_run": false
}
```

#### UACを拒否した場合

UACが拒否された場合は、通常権限で同じ操作を再試行しない。TCP connectなどの低権限代替が定義されている場合だけ、明示的にフォールバックする。

```json
{
  "ok": false,
  "errors": [
    {
      "code": "ELEVATION_CANCELLED",
      "message": "The user cancelled the Windows UAC elevation request.",
      "alternatives": ["tcp_connect_probe"]
    }
  ]
}
```

#### 実装方式

- 昇格対象は専用ヘルパーに限定する
- 任意のPythonコードや任意コマンドをヘルパーへ渡さない
- 操作種別、宛先、ポート、回数などを構造化JSONで渡す
- ヘルパー側でもPolicy Engineを再検証する
- 標準出力ではなく、検証済みのIPCまたは一時ファイルを利用する
- UAC起動失敗、キャンセル、タイムアウトを区別する

`ShellExecuteW(..., "runas", ...)`または署名済みの専用ヘルパーを利用できるが、PowerShellの任意文字列を組み立てて実行する方式は採用しない。

### 19.9 特権昇格の扱い（Linux/macOS）

Linux/macOSでも、sudo等を無断実行しない。必要な場合は、利用者が明示的に管理者/rootとして起動するか、OS標準の認証UIを使う専用ヘルパーを別途設計する。

将来的にヘルパーを導入する場合も、任意コマンドを受け取らず、許可された操作だけをIPC経由で提供する。

### 19.10 Python依存とOS依存の失敗を分離

```text
PYTHON_DEPENDENCY_MISSING
EXTERNAL_DEPENDENCY_MISSING
PRIVILEGE_REQUIRED
PLATFORM_UNSUPPORTED
FALLBACK_USED
```

Python依存がない場合は本体の自動インストールを試みる。外部実行ファイルがない場合と権限がない場合は、自動昇格やOSパッケージマネージャーの無断実行をせず、利用者へ案内する。

## 20. I18N実装・翻訳運用

### 20.1 対応ロケール

既存プロジェクトの38ロケールを対象とする。未翻訳の言語へ英語をフォールバックしない。

### 20.2 使用する既存スクリプト

```text
scripts/tool_json_i18n_batch.py  ツールJSONの一括翻訳
scripts/i18n_tools_check.py      ツールJSONの完全性チェック
scripts/po_i18n_batch.py         gettext POの一括翻訳
scripts/po_qc_summary.py         POの品質チェック
scripts/compile_locales.py       POからMOを生成
```

### 20.3 ツールJSONの処理手順

```bat
python scripts	ool_json_i18n_batch.py status
python scripts	ool_json_i18n_batch.py extract
python scripts	ool_json_i18n_batch.py translate
python scripts	ool_json_i18n_batch.py merge --apply
python scripts\i18n_tools_check.py --root .\src\uagent	ools --strict
```

### 20.4 完了条件

- 38ロケールのセクションが存在する
- 全言語のキー集合が英語と一致する
- 空の翻訳が存在しない
- プレースホルダーが一致する
- 保護対象の技術用語が壊れていない
- JSON構文が正しい
- `i18n_tools_check.py --strict`が成功する

### 20.5 翻訳不足時の動作

翻訳不足は実行時に英語へフォールバックせず、開発・CI時にエラーとして検出する。

```text
翻訳あり       → 指定ロケールで表示
翻訳不足       → I18N_TRANSLATION_MISSING
キー不一致     → I18N_KEY_MISMATCH
空文字         → I18N_EMPTY_TRANSLATION
プレースホルダー不一致 → I18N_PLACEHOLDER_MISMATCH
```

`po_i18n_batch.py`のバッチ分割リトライは、翻訳要求を小さく分割して再試行するためのものであり、別言語へのフォールバックではない。

## 21. TDD（テスト駆動開発）方針

ネットワークツール群は、実装より先にテストを定義し、TDDで作成する。実ネットワークへの送信を単体テストで行わず、依存関係、権限、外部コマンド、送信処理を分離してテスト可能にする。

### 21.1 Red-Green-Refactor

```text
1. Red       失敗するテストを書く
2. Green     最小限の実装でテストを通す
3. Refactor  動作を維持したまま設計を改善する
```

### 21.2 テスト層

```text
Unit Test
  入力検証、Policy Engine、結果変換、エラー分類、I18Nキー検証

Component Test
  Scapy、psutil、httpx、tshark/nmapアダプターをモック付きで検証

Integration Test
  ローカルのテストサーバー、loopback、fixture pcapで検証

Privilege Test
  Windows UAC、Npcap、権限不足を実環境または専用テスト環境で検証

E2E Test
  発見 → プローブ → 送信 → pcap解析 → 詳細解析の連携を検証
```

### 21.3 先に作成するテスト

#### 共通

- 必須パラメータ不足を拒否する
- 不正なIP、CIDR、ポート、回数、サイズを拒否する
- allowlist外の対象を拒否する
- `dry_run=true`では送信しない
- 送信数、送信間隔、タイムアウトの上限を守る
- 結果JSONの共通スキーマを満たす
- エラーコードが仕様どおりである

#### `network_discover`

- CIDRを正しく検証する
- socketバックエンドでTCP connectを実行できる
- nmap XMLを正常に解析できる
- nmap不在時にPythonバックエンドへフォールバックする
- 不正なXMLやタイムアウトを構造化エラーに変換する

#### `packet_probe`

- ICMP、ARP、TCP SYN、UDPの入力を検証する
- 権限不要のTCP connectへ切り替えられる
- 特権不足を`PRIVILEGE_REQUIRED`として返す
- Scapyの送受信をモックできる

#### `packet_send`

- `dry_run`でScapy送信関数が呼ばれない
- 許可されたパケット種別だけを受け付ける
- Raw payloadのサイズを制限する
- `allow_elevation`なしではUACを起動しない
- UAC拒否を`ELEVATION_CANCELLED`として返す
- 監査ログが生成される

#### `pcap_analyze`

- fixture pcapを読み取れる
- Ethernet、IPv4、IPv6、TCP、UDPを抽出できる
- 空ファイル、破損pcap、未知リンクタイプを処理できる
- 大きなpcapを逐次処理し、全件をメモリに保持しない

#### `protocol_inspect`

- tshark JSONを解析できる
- tshark不在を検出できる
- display filterを安全に渡せる
- JSON破損、タイムアウト、終了コード異常を処理できる
- Scapy等へのフォールバック時に`degraded=true`を返す

#### `local_network`

- psutilでインターフェースとアドレスを取得できる
- pyroute2がないLinux環境でも基本機能が動く
- Windows、Linux、macOSのアダプター選択を検証する
- OS固有機能を未対応環境で実行しない

#### I18N

- 38ロケールが存在する
- 全言語のキー集合が一致する
- 空翻訳がない
- プレースホルダーが一致する
- 保護対象の技術用語が保持される
- `i18n_tools_check.py --strict`が成功する

### 21.4 外部依存のテスト分離

外部コマンドやネットワークに依存するテストは、次の境界で差し替え可能にする。

```python
class CommandRunner:
    def run(self, argv: list[str], timeout: float) -> "CommandResult":
        raise NotImplementedError


class PacketBackend:
    def probe(self, request: dict) -> dict:
        raise NotImplementedError
```

本番では実装を注入し、単体テストではFake/Mockを注入する。

### 21.5 テスト用アーティファクト

```text
tests/network/
├── fixtures/
│   ├── minimal_ipv4.pcap
│   ├── minimal_ipv6.pcap
│   ├── malformed.pcap
│   ├── nmap_sample.xml
│   └── tshark_sample.json
├── fakes/
│   ├── fake_command_runner.py
│   └── fake_packet_backend.py
├── test_network_discover.py
├── test_packet_probe.py
├── test_packet_send.py
├── test_pcap_analyze.py
├── test_protocol_inspect.py
├── test_local_network.py
└── test_i18n.py
```

### 21.6 CI完了条件

```text
pytestが成功する
Python構文チェックが成功する
I18N strict checkが成功する
外部コマンドなしのテストが成功する
loopback限定の統合テストが成功する
権限不足・UAC拒否ケースが検証されている
送信系テストが実ネットワークへ到達しない
```

実ネットワークへの送信テストは通常CIでは実行せず、明示的に許可された専用環境でのみ実行する。

## 22. PCAPフィルター抽出

`pcap_analyze`は、入力pcapを条件でフィルターし、一致したパケットだけを別pcapへ保存できるようにする。

### 22.1 操作

```text
summary       概要
packets       パケット一覧
flows         フロー集計
statistics    統計
extract       条件一致パケットを別pcapへ抽出
```

### 22.2 入力例

```json
{
  "pcap_path": "capture.pcap",
  "operation": "extract",
  "output_path": "filtered.pcap",
  "filter": {
    "src_ip": "192.168.1.10",
    "protocol": "tcp",
    "dst_port": 443
  },
  "limit": 10000,
  "overwrite": false
}
```

### 22.3 フィルター項目

```text
src_ip
dst_ip
src_cidr
dst_cidr
protocol
src_port
dst_port
port
min_length
max_length
start_time
end_time
tcp_flags
vlan_id
contains_payload
```

### 22.4 ストリーム処理

大きなpcapを全件メモリに保持せず、`PcapReader`と`PcapWriter`で逐次処理する。

```python
from scapy.utils import PcapReader, PcapWriter

with PcapReader(input_path) as reader:
    with PcapWriter(output_path, append=False, sync=True) as writer:
        for packet in reader:
            if matches(packet, filter_spec):
                writer.write(packet)
```

### 22.5 出力例

```json
{
  "ok": true,
  "operation": "extract",
  "input_path": "capture.pcap",
  "output_path": "filtered.pcap",
  "read_packets": 15230,
  "written_packets": 842,
  "skipped_packets": 14388,
  "bytes_written": 521340,
  "truncated": false
}
```

### 22.6 安全制約

- `limit`で抽出件数を制限する
- 入力と出力が同一の場合は拒否する
- `overwrite=false`では既存ファイルを上書きしない
- 出力先の許可範囲を検証する
- パストラバーサルを拒否する
- 破損pcapと未知リンクタイプを構造化エラーにする
- 抽出処理と出力ファイルを監査ログへ記録する

### 22.7 tsharkとの使い分け

```text
IP/CIDR、TCP/UDP、ポート、サイズ、時間、TCPフラグ
  → Python + Scapy

複雑なWireshark display filter
  → tshark -Y（利用可能な場合のみ）
```

`tshark`がない場合でも、標準フィルターはPythonだけで利用可能にする。tsharkを使った場合は、使用したdisplay filterと実行結果を監査情報へ含める。

### 22.8 TDDテスト

- IPv4の条件抽出
- IPv6の条件抽出
- TCP/UDPポート抽出
- CIDR抽出
- 複合条件
- 一致パケットなし
- `limit`到達
- 空pcap
- 破損pcap
- 入力と出力が同一
- 出力先が既存
- 大容量pcapの逐次処理

## 23. LLMとのデータ交換最小化

ネットワークデータには、認証情報、Cookie、個人情報、内部ホスト名、通信内容が含まれる可能性がある。そのため、LLMへ返すデータは必要最小限にし、pcapやペイロード本体を既定では返さない。

### 23.1 基本原則

```text
処理はローカルで完結
LLMへは要約・件数・状態だけ返す
pcap本体はローカルパスで保持
Raw packetとpayloadは明示的な要求時だけ返す
返却サイズに上限を設ける
```

### 23.2 既定レスポンス

`pcap_analyze`の既定レスポンスは、次のようなメタデータだけにする。

```json
{
  "ok": true,
  "operation": "extract",
  "input_name": "capture.pcap",
  "output_name": "filtered.pcap",
  "read_packets": 15230,
  "written_packets": 842,
  "bytes_written": 521340,
  "protocols": {"tcp": 800, "udp": 42},
  "truncated": false
}
```

絶対パス、Raw packet、ペイロード、HTTP本文、Cookie、Authorizationヘッダーは既定で返さない。

### 23.3 詳細データの段階取得

詳細が必要な場合は、段階的に取得する。

```text
Level 0  件数・状態・統計
Level 1  通信相手、ポート、プロトコル
Level 2  パケットヘッダーの限定フィールド
Level 3  指定パケットのRaw/ペイロード（明示指定必須）
```

入力例：

```json
{
  "operation": "packets",
  "detail_level": 1,
  "limit": 100
}
```

### 23.4 機密情報保護

- payloadは既定で除外する
- HTTP本文、Cookie、Authorization、Set-Cookieをマスクする
- DNSクエリ名は必要に応じてハッシュ化またはドメイン部分のみ返す
- IPアドレスは設定によりマスクまたは匿名化する
- ファイル名と絶対パスを分離する
- ユーザー指定の出力パスをLLMへそのまま返さない
- バイナリをbase64化して自動返却しない

### 23.5 抽出pcapの扱い

`extract`はpcapをローカルに保存するが、LLMへファイル内容を自動転送しない。

```json
{
  "ok": true,
  "artifact": {
    "kind": "pcap",
    "name": "filtered.pcap",
    "local": true,
    "size": 521340,
    "sha256": "..."
  }
}
```

LLMへ内容を渡す場合は、別操作として明示的に指定する。

```json
{
  "operation": "read_packet_fields",
  "artifact": "filtered.pcap",
  "packet_indexes": [0, 3],
  "fields": ["ip.src", "ip.dst", "tcp.dstport"],
  "include_payload": false
}
```

### 23.6 サイズ制限

```text
max_response_bytes     既定 32 KiB
max_items              既定 100
max_payload_bytes      既定 0
max_raw_packets        既定 0
```

上限を超える場合は結果を切り詰め、`truncated=true`と件数を返す。自動的に追加ページをLLMへ送信しない。

### 23.7 ローカル成果物参照

大きな結果はLLMレスポンスに埋め込まず、ローカル成果物として保存する。

```text
LLMへ返す       → artifact_id、概要、件数、ハッシュ
ローカルに保存  → pcap、JSONL、詳細レポート
```

成果物の読み取りには、専用の明示的な操作とアクセス範囲チェックを要求する。

### 23.8 送信前の監査

LLMへ返す直前に、レスポンスを検査する。

```text
Raw bytesの有無
payloadの有無
秘密情報らしいヘッダー
過大な文字列
絶対パス
環境変数・資格情報
```

検出時はマスクまたは返却拒否し、監査ログには機密データそのものを記録しない。

### 23.9 TDDテスト

- 既定レスポンスにpayloadが含まれない
- 既定レスポンスに絶対パスが含まれない
- `detail_level=0`でヘッダー詳細が返らない
- `include_payload=false`が強制される
- CookieとAuthorizationがマスクされる
- `max_response_bytes`を超えない
- `limit`を超える項目を返さない
- pcap成果物がローカル保存され、内容が自動返却されない
- `truncated=true`が正しく付与される

## 24. 問題通信の検出

`pcap_analyze`に、問題の可能性がある通信をローカルで抽出する`detect`操作を追加する。検出は断定ではなく、ルール、証拠、スコアを返す。

### 24.1 基本方針

```text
pcapをローカルで処理
LLMへは検出結果の要約だけ返す
Raw packetとpayloadは既定で返さない
検出理由と証拠を返す
「悪性」と断定せず「要確認」と表現する
```

### 24.2 検出カテゴリ

```text
port_scan              短時間に多数ポートへ接続
host_scan              短時間に多数ホストへ接続
connection_burst       短時間の異常な接続数
repeated_failure       SYN/RSTや接続失敗の反復
unusual_port           非標準ポートへの通信
beaconing              一定間隔の反復通信
large_transfer         特定相手への大量転送
broadcast_anomaly      異常なブロードキャスト量
suspicious_dns         多数のNXDOMAIN、長いラベル、高頻度問い合わせ
cleartext_protocol     HTTP/FTP/Telnet等の平文プロトコル
long_lived_connection  長時間接続
```

### 24.3 API

```json
{
  "pcap_path": "capture.pcap",
  "operation": "detect",
  "rules": [
    "port_scan",
    "beaconing",
    "suspicious_dns"
  ],
  "thresholds": {
    "port_scan_distinct_ports": 20,
    "port_scan_window_seconds": 10,
    "beaconing_min_events": 5
  },
  "limit": 100
}
```

### 24.4 出力例

```json
{
  "ok": true,
  "operation": "detect",
  "findings": [
    {
      "id": "finding-001",
      "category": "port_scan",
      "severity": "medium",
      "confidence": 0.86,
      "src": "192.168.1.10",
      "target_count": 1,
      "distinct_ports": 43,
      "first_seen": "2026-01-01T12:00:01Z",
      "last_seen": "2026-01-01T12:00:09Z",
      "evidence": {
        "window_seconds": 10,
        "event_count": 43
      },
      "recommendation": "Review the source host and intended scan activity."
    }
  ],
  "summary": {
    "packets_analyzed": 15230,
    "findings": 1,
    "high": 0,
    "medium": 1,
    "low": 0
  }
}
```

### 24.5 スコアと深刻度

ルールごとに証拠を加点し、固定の閾値で深刻度を分類する。

```text
low       要確認だが単独では問題と判断しにくい
medium    複数の異常指標が一致
high      強い異常指標が複数一致
critical  専用検知エンジン等で重大シグネチャ一致
```

スコアだけで悪性判定を行わず、必ず以下を併記する。

```text
category
severity
confidence
evidence
first_seen / last_seen
recommendation
```

### 24.6 実装バックエンド

```text
標準検出       Python + Scapy + 統計処理
詳細プロトコル tshark（存在する場合）
シグネチャ検知 Suricata（存在する場合）
通信ログ生成   Zeek（存在する場合）
```

外部エンジンがない場合でも、ポートスキャン、接続バースト、ビーコン、転送量、DNS統計などの標準検出は実行可能にする。

### 24.7 誤検知対策

- ルールごとに閾値を指定可能にする
- 除外CIDR、除外ホスト、許可ポートを設定可能にする
- TCPの未許可ポートは初期SYNで確定したサーバー側方向だけを判定し、逆方向のエフェメラルポートを除外する
- 初期SYNがキャプチャに存在しないTCP通信は、方向を確定できないため未許可ポート検出の対象外にする
- UDPはTCPのような接続確立がないため、パケットの宛先ポートとして別カテゴリで扱う
- サーバー、バックアップ、監視、パッチ配布などの既知パターンを除外できるようにする
- 検出結果に証拠を必ず含める
- `confidence`と`severity`を分離する
- 断定的な「攻撃」「マルウェア」表現を既定で使用しない

### 24.8 LLMへの返却

LLMにはfindingの要約だけ返す。パケット列やpayloadは自動送信しない。

```text
返す       → category、severity、confidence、対象、時刻、証拠、推奨対応
返さない   → Raw packet、payload、認証情報、HTTP本文
```

### 24.9 TDDテスト

- 少数ポートへの通常通信をport_scanと判定しない
- 閾値を超えたポート接続を検出する
- 時間窓の境界を正しく処理する
- 一定間隔の通信をbeaconing候補として検出する
- DNS NXDOMAIN率を計算する
- 大量転送を検出する
- 除外CIDRが適用される
- 外部エンジン不在でも標準検出が動く
- payloadが結果に含まれない
- 同一pcapで検出結果が再現する

## 25. 人間確認とOS権限の分離

`human_ask`は特権操作の明示的な同意確認に使用する。ただし、`human_ask`自体はOS権限を付与しない。

```text
human_ask             ユーザーの意思確認
UAC / sudo / setcap   OS権限の取得
network helper        特権ネットワーク処理
```

### 25.1 共通フロー

```text
1. preflightで依存・権限・代替手段を確認
2. human_askで操作内容を表示して確認
3. OS固有の固定ヘルパーを起動
4. ヘルパー側でリクエストとPolicyを再検証
5. 結果JSONだけを返す
```

`human_ask`の許可だけで権限取得済みとは判断しない。

### 25.2 OS別

```text
Windows:
  human_ask → ShellExecuteW("runas") → UAC → 固定helper

Linux:
  human_ask → setcap済みhelper
  またはユーザーがsudoでuagを起動

macOS:
  human_ask → sudo起動済みhelper
  将来はAuthorization Servicesを検討
```

### 25.3 禁止事項

- `human_ask`でsudoパスワードを取得しない
- パスワードを保存しない
- ユーザー確認なしにUAC/sudoを起動しない
- 任意コマンドを昇格しない
- uag本体全体を無条件に昇格しない

### 25.4 権限不足時

OS権限が取得できない場合は、次のいずれかを行う。

```text
低権限の代替へフォールバック
PRIVILEGE_REQUIREDを返す
ユーザー向けの手動導入手順を返す
```

パスワード入力を自動化せず、権限不足を成功として扱わない。

## 25. 現行実装ステータス

### 実装済み

- `pcap_analyze`: summary/statistics/flows/packets/extract/detect/impact
- `capture_analyze`: offline pcapのsummary/flows/detect/impact一括実行とlocal_network相関
- `capture_analyze`の通信分類: normal/review/suspicious/unknown（攻撃断定ではなく要確認分類）
- pcapフィルター: IP、CIDR、プロトコル、ポート、サイズ条件。`flows`にも適用
- 問題通信検出: port_scan、host_scan、connection_burst、beaconing、suspicious_dns、large_transfer、cleartext_protocol、repeated_failure、unusual_port、tcp_retransmission、long_lived_connection、broadcast_anomaly、syn_flood_candidate、rtt_anomaly、protocol_anomaly
- TCP再送候補の分類: confirmed / possible / capture_duplicate とconfidenceを返す
- TCPのSYN Flood判定: 逆方向SYN-ACKとポート組み合わせを照合
- TCPの未許可ポート: 初期SYNでサーバー方向を確定し、逆方向エフェメラルポートを除外
- Well-known/Commonサービスポート: 57ポートとサービス名を内蔵。サイト固有ポートで上書き可能
- ブロードキャスト除外: NetBIOS、SSDP、mDNS、UDP/17500などを既知ポートとして扱う
- SQLiteメタデータキャッシュ: `%USERPROFILE%\.uag\cache\pcap\`または`UAGENT_PCAP_CACHE_DIR`
- `local_network`: interfaces/connections/correlate
- 自端末のPID・プロセス名との相関
- Windows Wi-FiのTSharkキャプチャ実証
- Zeek/Suricata/TShark/Nmapの外部実行ファイル検出とフォールバック
- 38言語I18Nと本体の依存関係自動インストール

### 制約

- pcapだけでは他端末上のプロセス名は取得できない
- 他端末のプロセス特定には、明示的に導入した端末エージェントが必要
- TCP再送はNICオフロード、キャプチャ欠落、重複の影響を受けるため「再送候補」として扱う
- 外部CLI（TShark、Zeek、Suricata、Nmap）は本体から無断インストールしない
- 特権昇格はWindows UAC専用ヘルパーを含め、操作単位で明示同意を要求する

### 次期実装

1. impactランキングとプロセス相関の一括出力強化
1. 通信分類の閾値・誤検知評価と運用チューニング
1. loopback限定のライブキャプチャ統合
1. 他端末用の明示的な端末エージェント設計

</details>

<details>
<summary>docs/packet-probe-design.md</summary>

### packet_probe 設計

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

</details>

<details>
<summary>docs/packet-send-design.md</summary>

### packet_send 設計

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

</details>

<details>
<summary>docs/pcap-analyze-design.md</summary>

### pcap_analyze 設計

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

</details>

<details>
<summary>docs/protocol-inspect-design.md</summary>

### protocol_inspect 設計

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

</details>

<details>
<summary>docs/traffic-monitor-design.md</summary>

### traffic_monitor / threat_detect 設計

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
1. `conn.log`、`dns.log`などを生成
1. Pythonで読み取り、正規化・集計・通知

## threat_detect: Suricata

### 役割

- IDS/IPS
- ルールベース検知
- EVE JSON出力
- アラート・フローログ生成

### Python連携

1. Suricataを実行
1. `eve.json`をJSON Linesとして読む
1. アラートを共通イベント形式に変換

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

</details>

<details>
<summary>docs/web-request-design.md</summary>

### web_request / web_intercept 設計

## 目的

HTTP/API確認にはhttpx、必要に応じてmitmproxyを利用する。

## web_request: httpx

### 用途

- HTTPステータス確認
- ヘッダー取得
- API呼び出し
- TLS接続確認
- JSONレスポンス取得

### 入力例

```json
{
  "url": "https://example.com/api/status",
  "method": "GET",
  "headers": {},
  "timeout": 5,
  "follow_redirects": false
}
```

### 安全制御

- URLスキームを`http`/`https`に限定
- 許可ドメインを設定可能にする
- リダイレクト回数を制限
- レスポンスサイズを制限
- 認証情報をログに出さない

## web_intercept: mitmproxy

### 用途

- HTTP/HTTPS通信の記録
- テスト用リクエスト変更
- APIデバッグ
- モック・再送

Pythonアドオンでリクエスト・レスポンスを処理する。

## Python依存

```text
httpx
mitmproxy（必要時）
```

</details>
