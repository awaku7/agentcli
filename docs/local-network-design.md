# local_network 設計

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
