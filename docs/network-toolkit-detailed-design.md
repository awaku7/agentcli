# Network Toolkit 詳細設計

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
- pcapフィルター: IP、CIDR、プロトコル、ポート、サイズ条件。`flows`にも適用
- 問題通信検出: port_scan、host_scan、connection_burst、beaconing、suspicious_dns、large_transfer、cleartext_protocol、repeated_failure、unusual_port、tcp_retransmission、long_lived_connection、broadcast_anomaly、syn_flood_candidate、rtt_anomaly、protocol_anomaly
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

1. `capture_analyze`一括操作
1. TCP再送のconfirmed/possible/capture_duplicate分類
1. impactランキングとプロセス相関の一括出力
1. normal/review/suspicious/unknownの通信分類
1. 他端末用の明示的な端末エージェント設計
