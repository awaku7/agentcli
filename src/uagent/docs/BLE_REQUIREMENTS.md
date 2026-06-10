# BLEツール（ble_ops）要件定義書

本ドキュメントは、ローカルツール実行エージェント（uagent）にBluetooth Low Energy（BLE）操作機能を追加するためのツール `ble_ops` の要件定義書です。

---

## 1. 目的
uagentが動作するローカルPC（Windows, macOS, Linux/Raspberry Pi）から、周辺のBLEデバイスを探索し、接続、およびGATTデータの読み書きを行えるようにすることで、スマートホームデバイスやIoT機器との直接連携を可能にします。

---

## 2. 対象プラットフォームと動作要件
- **OS**: Windows 10/11, macOS, Linux (Raspberry Pi OS を含む)
- **Python**: 3.11+
- **主要依存ライブラリ**: `bleak` (Bluetooth Low Energy platform Agnostic Klient)
- **ハードウェア**: Bluetooth 4.0 (BLE) 以上に対応したBluetoothアダプター

---

## 3. 機能要件

### 3.1. 周辺デバイスのスキャン（scan）
- 周辺に存在するアドバタイズ中のBLEデバイスを探索します。
- **取得情報**:
  - デバイス名（取得できない場合は "Unknown"）
  - アドレス（Windows/LinuxはMACアドレス、macOSはUUID）
  - RSSI（電波強度）
- **パラメータ**:
  - `timeout`: スキャンを実行する秒数（デフォルト: 5秒）

### 3.2. GATTキャラクタリスティックの読み取り（read）
- 指定したBLEデバイスに接続し、特定のサービス配下にあるキャラクタリスティックの値を読み取ります。
- **パラメータ**:
  - `address`: 接続先デバイスのアドレス（MACアドレスまたはUUID）
  - `char_uuid`: 読み取り対象のキャラクタリスティックUUID
  - `timeout`: 接続・読み取りのタイムアウト秒数（デフォルト: 5秒）
- **出力形式**:
  - 16進数文字列（hex）
  - テキスト（UTF-8デコード、デコード不可な文字は代替文字に置換）

### 3.3. GATTキャラクタリスティックへの書き込み（write）
- 指定したBLEデバイスに接続し、特定のキャラクタリスティックにデータを書き込みます。
- **パラメータ**:
  - `address`: 接続先デバイスのアドレス（MACアドレスまたはUUID）
  - `char_uuid`: 書き込み対象のキャラクタリスティックUUID
  - `data_hex`: 書き込むデータの16進数文字列（例: `010203`）
  - `timeout`: 接続・書き込みのタイムアウト秒数（デフォルト: 5秒）

---

## 4. 非機能要件・設計制約

### 4.1. 遅延インポート（Lazy Import）
- `bleak` ライブラリがインストールされていない環境でも、uagentの起動や他のツールのロードを妨げないよう、`run_tool` 内部で `bleak` をインポートします。未インストールの場合は、ユーザーに `pip install bleak` を促すエラーメッセージを返します。

### 4.2. 同期・非同期の変換
- `bleak` は `asyncio` ベースの非同期APIを提供しますが、uagentのツール実行インターフェースは同期関数（`run_tool`）です。
- ツール内部で `asyncio.run()` を使用して非同期処理を同期的に実行します。
- Windows環境でのイベントループの競合や不具合を防ぐため、必要に応じて `WindowsSelectorEventLoopPolicy` を適用します。

### 4.3. OSごとのアドレス仕様の差異
- Windows/Linuxでは `XX:XX:XX:XX:XX:XX` 形式のMACアドレスを使用します。
- macOSではOSのセキュリティ制限により、MACアドレスの代わりに `E621A1F2-C042-4ECB-B512-B30634991AB4` のようなUUIDを使用します。
- この差異をツールの説明（`TOOL_SPEC`）に明記し、LLMが適切にアドレスを指定できるようにします。

### 4.4. Linux/Raspberry Pi での権限考慮
- Linux環境で実行する際、一般ユーザー権限ではBluetoothソケットへのアクセスが拒否される場合があります。
- 権限エラー（PermissionErrorやDBusのアクセス拒否など）を検知した場合は、エラーレスポンスの理由（Reason）や詳細メッセージに、ユーザーを `bluetooth` グループへ追加するコマンドや、`setcap` によるPythonバイナリへの権限付与方法などの具体的な解決策を含めて返します。これにより、ユーザーやLLMが原因と対処法を即座に把握できるようにします。

### 4.5. macOS での権限考慮
- macOSでは、アプリ（ターミナル、VS Code、Pythonを実行するプロセスなど）がBluetoothにアクセスする際、OSの「システム設定 ＞ プライバシーとセキュリティ ＞ Bluetooth」でのアクセス許可が必要です。
- 権限がない場合、`bleak` はデバイスを検出できなかったり、接続時にエラーを発生させたりします。
- 権限エラー（またはmacOS環境でスキャン結果が空、もしくは接続失敗が続く場合）を検知した場合は、エラーレスポンスの理由（Reason）や詳細メッセージに、「システム設定 ＞ プライバシーとセキュリティ ＞ Bluetooth」で実行中のターミナルやIDE（VS Codeなど）のアクセス許可が有効になっているか確認するよう促すガイダンスを含めて返します。

---

## 5. ツール仕様（TOOL_SPEC）

```json
{
  "tool_level": 1,
  "tool_genre": "devel",
  "function": {
    "name": "ble_ops",
    "description": "Bluetooth Low Energy (BLE) デバイスのスキャン、接続、GATTデータの読み書きを行います。Windows/LinuxではMACアドレス、macOSではUUIDをアドレスとして指定します。",
    "parameters": {
      "type": "object",
      "properties": {
        "action": {
          "type": "string",
          "enum": ["scan", "read", "write"],
          "description": "実行する操作。scan: 周辺デバイス探索, read: キャラクタリスティック読み取り, write: 書き込み"
        },
        "timeout": {
          "type": "integer",
          "default": 5,
          "description": "スキャンや接続のタイムアウト秒数"
        },
        "address": {
          "type": "string",
          "description": "対象デバイスのMACアドレス（Windows/Linux）またはUUID（macOS）"
        },
        "char_uuid": {
          "type": "string",
          "description": "読み書き対象のGATTキャラクタリスティックUUID"
        },
        "data_hex": {
          "type": "string",
          "description": "書き込むデータの16進数文字列（例: '010203'）。action='write' の時のみ必須"
        }
      },
      "required": ["action"]
    }
  }
}
```
