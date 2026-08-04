# Pythonライブラリ中心の実装調査

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
2. ScapyでARP/ICMP/TCPプローブを追加する
3. nmapは`advanced`モードの任意依存にする

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
