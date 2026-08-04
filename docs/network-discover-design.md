# network_discover 設計

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
