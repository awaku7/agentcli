# pybitchat — BLE Mesh Communication

`pybitchat` enables peer-to-peer messaging over BLE Mesh, compatible with the [bitchat](https://bitchat.app) protocol. Messages are exchanged directly between nearby devices over Bluetooth Low Energy, and optionally relayed via Nostr for longer-distance communication.

> **Note**: Bitchat is a separate communication protocol managed by the bitchat project. uag integrates bitchat as a set of tool plugins — this page covers the uag-side usage.

## Tools

Two tool plugins provide the bitchat interface:

| Tool | Genre | Description |
|------|-------|-------------|
| `pybitchat_subscribe` | comm | Start/stop/monitor the BLE Mesh node. Chat mode for forwarding user input. |
| `pybitchat_send` | comm | Send text messages, announcements, or files over the mesh. |

## Quick Start

### 1. Start the node

```python
pybitchat_subscribe action="start" nickname="my-node"
```

This starts BLE advertising and scanning. The node appears as `my-node` to peers.
By default it uses the `mainnet` network. Use `network="testnet"` for testing.

**Status check**:

```python
pybitchat_subscribe action="status"
```

**Stop**:

```python
pybitchat_subscribe action="stop"
```

### 2. Send messages

Once the node is running:

```python
pybitchat_send type="text" payload="Hello from uag!"
```

This broadcasts to all nearby peers. To send to a specific peer:

```python
pybitchat_send type="text" payload="Hi!" recipient="<peer-id-hex>"
```

### 3. Send announcements

Announce your presence with a nickname:

```python
pybitchat_send type="announce" payload="my-node"
```

### 4. Enable chat mode

Chat mode forwards every user input to the mesh as a broadcast text message.
Messages received from the mesh are displayed in the terminal.

```python
pybitchat_subscribe action="chat_mode" on=true
```

To disable:

```python
pybitchat_subscribe action="chat_mode" on=false
```

### 5. Send files

```python
pybitchat_send type="file" payload="C:/path/to/file.pdf"
```

Files are encoded as TLV payload and transmitted to all connected peers.
Maximum file size: 1 MB.

## Nostr Transport

In addition to BLE, pybitchat can relay messages over Nostr relays for long-distance communication.

### Start with Nostr

```python
pybitchat_subscribe action="start" nickname="my-node" nostr=true
```

Optional: specify custom relays:

```python
pybitchat_subscribe action="start" nickname="my-node" nostr=true nostr_relays="relay1.com,relay2.com"
```

### Send via Nostr

By default, `pybitchat_send` uses BLE only. To send over Nostr:

```python
pybitchat_send type="text" payload="Hello Nostr!" via="nostr"
```

To send over both transports simultaneously:

```python
pybitchat_send type="text" payload="Hello world!" via="both"
```

### Nostr Pubkey

When Nostr transport is running, the node gets a keypair. Use the pubkey for targeted messaging:

```python
pybitchat_send type="text" payload="Direct message" recipient="<64-char-hex-pubkey>" via="nostr"
```

When recipient is a 64-character hex string, the message is encrypted using kind-1059 (NIP-17-compatible direct message).

## Geo Channels (Nostr only)

When Nostr transport is enabled, you can join geo-based channels using the `:bitchat geo` CLI commands.

### Join a geo channel

List available Geohash candidates in your area:

```
:bitchat geo join
```

This detects position via GPS sensor or IP geolocation and lists available geohash channels across precision levels (e.g. `#xn`, `#xn0m`, `#xn0m7`, `#mesh`).

Join a specific geohash channel:

```
:bitchat geo join xn0m7
```

Or specify coordinates manually:

```
:bitchat geo join 35.6762 139.6503 6
```

The command calculates a geohash and subscribes to Nostr messages from users in that area.

### Leave a geo channel

```
:bitchat geo leave xn76gg
```

### List active geo channels

```
:bitchat geo list
```

### Recommended precision values

| Precision | Approximate area |
|-----------|-----------------|
| 4 | ~39 km |
| 5 | ~4.9 km |
| 6 | ~1.2 km |
| 7 | ~152 m |
| 8 | ~38 m |

## CLI Commands (`:` short commands)

| Command | Description |
|---------|-------------|
| `:bitchat start [nickname] [--nostr] [--network <mainnet|testnet>]` | Start the BLE Mesh node |
| `:bitchat stop` | Stop the BLE Mesh node |
| `:bitchat on` | Enable chat mode (user input forwarded to mesh) |
| `:bitchat off` | Disable chat mode |
| `:bitchat status` | Show node state, chat mode, peers, Nostr status |
| `:bitchat peers` | List discovered Nostr bitchat peers |
| `:bitchat geo join [<geohash>|lat lng [prec]]` | List geo candidates or join a geohash channel |
| `:bitchat geo leave <geohash>` | Leave a geohash channel |
| `:bitchat geo list` | List active geo channels |
| `:nostr connect [relays]` | Connect to Nostr relays |
| `:nostr status` | Show Nostr status |
| `:nostr post <message>` | Post public text note (Kind 1) to Nostr |
| `:nostr timeline [limit]` | Fetch recent public notes from Nostr relays |
| `:nostr disconnect` | Disconnect from Nostr relays |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  pybitchat_subscribe                 │
│  ┌─────────────────────┐  ┌──────────────────────┐  │
│  │    BLE Mesh (bleak) │  │  Nostr Transport     │  │
│  │  • advertise/scan   │  │  • relay messages    │  │
│  │  • fragmented send  │  │  • encrypted DMs     │  │
│  │  • message relay    │  │  • geo channels      │  │
│  └─────────┬───────────┘  └──────────┬───────────┘  │
│            │                         │              │
│            └──────────┬──────────────┘              │
│                       │                            │
│              ┌────────▼────────┐                    │
│              │  Outbound Queue │                    │
│              └────────┬────────┘                    │
│                       │                            │
│              ┌────────▼────────┐                    │
│              │  Chat Mode      │                    │
│              │  (input→mesh)   │                    │
│              └─────────────────┘                    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  pybitchat_send                      │
│  Enqueue message → outbound queue → BLE / Nostr     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  pybitchat_shared                     │
│  • Node identity (Noise X25519 + Ed25519 signing)   │
│  • BLE service (advertise/scan/connect)             │
│  • Fragment assembly                                │
│  • File transfer (TLV encoding)                     │
│  • Peer discovery & nickname tracking               │
│  • Auto-install dependencies (bleak, cryptography,  │
│    bitchat-protocol)                                │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  bitchat_noise                        │
│  Noise XX handshake (X25519 + ChaChaPoly + SHA256)  │
│  Wire-compatible with official bitchat app           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  bitchat_geo                          │
│  GeoHash encoding/decoding                          │
│  Geo channel management (join/leave/list)           │
└─────────────────────────────────────────────────────┘
```

## Dependencies

Dependencies are auto-installed on first use:

| Package | Purpose |
|---------|---------|
| `bleak` | BLE (Bluetooth Low Energy) communication |
| `cryptography` | Noise XX handshake, encryption, key management |
| `bitchat-protocol` | Protocol definitions (packet encoding/decoding) |

## Wire Format

pybitchat is wire-compatible with the official bitchat app:

- **BLE**: Advertises service UUID `F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5C` (mainnet) / `F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5A` (testnet)
- **Protocol**: `Noise_XX_25519_ChaChaPoly_SHA256` handshake
- **Packet format**: BitchatPacket (version 1) with Ed25519 signatures
- **Fragmentation**: Automatic for payloads > 480 bytes
- **File transfer**: TLV-encoded (file name, size, MIME type, content)

## Security Notes

- Each node generates a fresh X25519 + Ed25519 keypair on first run.
- Direct messages use Noise XX handshake for end-to-end encryption.
- Messages are signed with Ed25519 for authenticity.
- The identity keypair is ephemeral (per process). No persistent key storage.
- Nostr messages to specific pubkeys use kind-1059 encrypted DMs.

## See also

- [COMMUNICATION.md](COMMUNICATION.md) — Other communication tools (Bluesky, Discord, Gmail, Teams)
- [IOT_USECASE.md](IOT_USECASE.md) — IoT device control tools

## Development, audit, and interoperability

This section consolidates the former audit, Android interoperability investigation, and debugging procedure documents. The operational sections above describe the user-facing behavior; this section records implementation status, security considerations, and device-test procedures.

### pybitchat / bitchat 実装監査

## 対象

- `src/uagent/tools/pybitchat_shared.py`
- `src/uagent/tools/bitchat_noise.py`
- `../bitchat` の Swift 実装
- `docs/BITCHAT.md`

再調査では、プロトコル定義、BLE受信処理、署名検証、Noise DM、ファイル転送、relay処理を比較した。

## 対応状況

今回、以下を実装側で対応した。

- ANNOUNCE / MESSAGE / FILE_TRANSFER / LEAVE / FRAGMENT の署名検証
- Noise DMの平文フォールバック廃止
- BLE通知のpeer別ストリーム再構成
- TTLを使った署名保持relayと受信元への再送抑止
- 受信ファイルの同名上書き防止
- BLEサービスの二重起動防止
- BLEサービス異常終了時のrunning状態修正
- BLEの公開メッセージをNostrへブリッジ
- Noiseの1024件sliding replay window
- Noise handshakeのtimeout / state reset / 競合アクセス保護
- Noise handshakeメッセージの厳密な長さ検証
- Noise sessionの有効期限
- Noise outer frameの署名なし送信
- 255バイトを超えるBLE Noise DMのチャンク分割
- identity秘密鍵のOS credential store保存（非対応環境は.env.sec方式へフォールバック）
- Noise XX handshakeの空payload認証タグ（message 2=96バイト、message 3=64バイト）
- cryptographyのRaw serialization APIを使った鍵エンコード
- Noise実装を`bitchat_noise.py`へ一本化し、旧重複状態機械を削除

Noiseの外側フレーム自体は、現行プロトコルどおり署名対象外としている。Noiseのハンドシェイクと暗号化フレームは、TTLを保持したrelay対象として追加した。実機相互接続では、引き続きNoiseのreplay制御と複数hop通信を確認する必要がある。

## 未対応・残課題

主要な明白なバグは対応済みだが、以下は未完了である。

1. **実機相互接続テスト**

   - Android / iOSとの実BLE通信
   - 複数hopのrelay
   - Noiseハンドシェイクの複数hop動作

1. **Noiseの実機replay相互接続確認**

   - 1024件sliding windowは実装済み
   - Android / iOS間で順不同配送と重複nonceを実機確認する必要がある

1. **Fragment再構成の入力検証**

   - 同一転送内で `total_fragments` が変わらないことの検証
   - 総サイズ上限
   - 異常な断片系列の拒否

1. **relayの経路制御**

   - 現在はTTLと受信元除外を備えた簡易フラッディング
   - `../bitchat` の詳細なrelay policyや宛先最適化は未対応

1. **署名鍵の永続的なpinning / TOFU制御**

   - 現在は実行中のANNOUNCEで学習した署名鍵を利用
   - 再起動後の鍵ローテーション・なりすまし耐性は要検討

したがって、現状は主要な明白なバグを修正した段階であり、プロトコル互換性とセキュリティの最終確認は未完了である。

## 確定度が高い問題

### 1. 受信パケットの署名検証がない

`pybitchat_shared.py:1200` 付近では、受信通知を `decode()` した後、そのまま `_dispatch()` に渡している。

```python
pkt = decode(bytes(data))
if pkt is not None:
    _dispatch(pkt)
```

`bitchat_protocol.decode()` はパケット構文を解析するだけで、署名を検証しない。`_dispatch()` でも以下の受信パケットを署名検証なしで処理している。

- `ANNOUNCE`
- `MESSAGE`
- `FILE_TRANSFER`

`../bitchat` 側では、`BLEAnnounceHandler`、`BLEPublicMessageHandler`、`BLEFileTransferHandler` などで署名検証を行っている。

**影響:** peerのなりすまし、偽メッセージ、偽ファイル転送。

> 注意: `NOISE_HANDSHAKE` / `NOISE_ENCRYPTED` の外側パケットが署名なしなのは、現行プロトコル設計上の扱いであり、公開パケットの署名検証欠如とは別問題。

### 2. Noise DMが平文にダウングレードする

`pybitchat_shared.py:1390` 前後では、Noiseセッションが確立できない場合に、通常の `MESSAGE` パケットとして送信する経路がある。

```python
# Fall through to plain-text DM
```

`../bitchat` 側ではプライベート通信を `noiseEncrypted` に限定しており、暗号化できない場合に平文送信しない。

**影響:** DMの内容が暗号化されず、中継peerなどから読める。

### 3. Mesh relay処理が実際のBLE受信経路に接続されていない

Python側には以下のクラスが存在する。

```python
class MessageDeduplicator
class RelayController
```

しかし、これらは主に単体テストから利用されており、BLE受信処理 `_dispatch()` から使われていない。

`_dispatch()` は受信後に表示、LLM注入、ファイル保存、Noise処理を行うだけで、以下を実行していない。

- 他のBLE peerへの再送
- TTL減算
- relay対象判定
- 送信元への再送抑止
- relay jitter

`docs/BITCHAT.md` では「message relay」と説明されているため、ドキュメントと実装も不一致。

**影響:** 複数hopのmeshとして機能せず、直接接続されたpeer間通信に近い。

### 4. BLE通知のストリーム再構成がない

Python側はBLE通知1回分を完全なパケットとしてdecodeしている。

```python
pkt = decode(bytes(data))
```

一方、`../bitchat` 側には以下がある。

- `NotificationStreamAssembler`
- `bufferNotificationChunk`
- peerごとの受信バッファ
- ヘッダーからのフレーム長判定
- 複数通知の再構成

MTU境界で分割された通知や複数フレームが連結された通知を、Python側は正しく扱えない可能性がある。

**影響:** 大きなパケット、断片化パケット、Androidとの通信で受信失敗。

### 5. 受信ファイルを同名上書きする

Python側は次のように保存している。

```python
save_path = os.path.join(_DOWNLOAD_DIR, safe_name)
with open(save_path, "wb") as f:
    f.write(fdata)
```

`../bitchat` 側には既存ファイルとの衝突を避ける `uniqueFileURL()` がある。

**影響:** 同名ファイルの受信時に、既存のダウンロードファイルが無警告で消える。

## 追加で確認できた問題

### 6. `start()` の二重起動

BLEがすでに動作中でNostrだけを追加起動するために、次を呼ぶケースを考える。

```python
start(nostr=True)
```

`_RUNNING` がすでに `True` で、Nostrが停止中の場合、Nostrだけを追加するのではなく、BLEリスナースレッドをもう一つ作る経路がある。

**影響:** BLEスキャンの二重化、peer接続状態のリセット、重複通知、グローバル状態の競合。

### 7. `_NOSTR_BRIDGE` が実際には使われていない

起動時に次の設定を行っている。

```python
_NOSTR_BRIDGE = True  # enable BLE->Nostr forwarding
```

しかし、このフラグを参照して受信BLEメッセージをNostrへ転送する処理は確認できない。Nostrへ送られるのは、主に `enqueue_send()` を明示的に通った送信である。

**影響:** 想定されるBLE→Nostrブリッジが機能しない。

### 8. BLEサービスの起動失敗を隠して `running` のままになる

リスナースレッドは例外を握りつぶしている。

```python
def _listener_loop(...):
    try:
        loop.run_until_complete(...)
    except Exception:
        pass
```

一方、`start()` はBLEスレッド起動直後に `_RUNNING = True` にする。

**影響:** BLEスキャン開始失敗や依存関係エラーが起きても、`status()` が `running` を返す可能性がある。

## 優先順位

1. 受信パケットの署名検証
1. Noise DMの平文フォールバック廃止
1. BLE通知ストリーム再構成
1. 実際のmesh relay処理の接続
1. ファイル名衝突時の上書き防止
1. `start()` の二重起動防止
1. BLE起動失敗の状態反映

## テスト状況

以下の既存テストは通過した。

- `tests/test_pybitchat_protocol.py`
- `tests/test_pybitchat_fragment.py`
- `tests/test_pybitchat_noise.py`
- `tests/test_pybitchat_relay.py`
- プロジェクト全体のpytest

ただし、既存テストは主にパケットencode/decode、Noise状態機械、断片再構成、relayクラス単体を対象としている。実際のBLE通知、署名検証、複数peer relay、Android相互接続は十分にカバーしていない。

この監査ではコード変更・修正・コミットは行っていない。

### bitchat Android / Python Noise 相互運用調査

## 対象

- Android: `permissionlesstech/bitchat-android`
- 確認コミット: `c02dda308e8a1404d6a6697a4853825723a7413e`
- ローカルclone: `bitchat-android/`
- Python側: `src/uagent/tools/bitchat_noise.py`、`src/uagent/tools/pybitchat_shared.py`

## Android側で確認した仕様

### Noise

- プロトコル名: `Noise_XX_25519_ChaChaPoly_SHA256`
- msg1: 32バイト
- msg2: 96バイト（空payloadの認証タグ16バイトを含む）
- msg3: 64バイト（空payloadの認証タグ16バイトを含む）
- Noiseハンドシェイクはrecipient ID宛てである必要がある
- Noiseハンドシェイクパケットは署名検証の対象外

### BLEパディング

`BLEPacketPaddingPolicy.kt` では、以下だけをパディングする。

- `NOISE_HANDSHAKE`
- `NOISE_ENCRYPTED`

`MessagePadding.kt` のブロックサイズは次の通り。

```text
256 / 512 / 1024 / 2048
```

パディングはPKCS#7形式で、パディング長のバイトを末尾に繰り返す。

## 発生していた現象

Pythonからmsg2を送信すると、Androidからmsg3ではなくmsg1が再送された。

```text
Python: msg2 len=80
Python: wire=256
Android: msg1 len=32 を再送
```

Python側では、32バイトの再送msg1をmsg3と誤認し、`msg3 too short: 32` になっていた。

## Python側で実施した修正

### 1. Noise初期ハッシュ

Noise仕様では、プロトコル名がHASHLEN以下の場合、SHA-256化せずゼロパディングする。

`Noise_XX_25519_ChaChaPoly_SHA256` はちょうど32バイトなので、Androidと同じくプロトコル名をそのまま初期値として使用するよう修正した。さらにAndroidの `HandshakeState.start()` は空のprologueでも `MixHash` を実行するため、Python側でも開始時に `SHA256(h || empty)` を適用するよう修正した。

### 2. Noise BLEパディング

Python側の一般パディングは128バイト基準だったため、Noise送信では使用せず、Android互換の256バイトPKCS#7パディングを明示的に適用するよう修正した。

### 3. 再送msg1の処理

responderのpending状態で32バイトを受信した場合、msg3として処理せず、再ハンドシェイク開始として処理するよう修正した。

### 4. 失敗状態の破棄

msg2/msg3処理に失敗した場合、pending Noiseセッションを破棄し、次回のハンドシェイクを新しい状態から開始するよう修正した。

### 5. 重複パケット抑止

BLE再送で同一メッセージが複数回届く場合に、表示・LLM注入が重複しないよう、送信元・種別・タイムスタンプ・payloadによる重複排除を追加した。

## 検証結果

- Python構文チェック: 成功
- Noise XX Python内部self-test: 成功
- msg1/msg2/msg3: `32 / 96 / 64`
- Android側の仕様コードとの照合: 完了

## 現在の未解決点

Android側では、Pythonから256バイトのmsg2を送信した後もmsg1が再送され、msg3が返らない場合がある。

このため、残る確認対象はAndroid端末上の実行時処理である。

- `BinaryProtocol.decode` の実際の結果
- `PacketRelayManager.isPacketAddressedToMe` のrecipient ID判定
- `NoiseSessionManager.processHandshakeMessageWithResult` の例外
- `BluetoothPacketBroadcaster` / GATT送信経路でのmsg2受信状況

GitHubコードから仕様は確認できるが、Androidが実行時にmsg2を拒否した直接の理由は端末ログがないと確定できない。

### bitchat Android Noise DM 相互接続デバッグ手順

## 目的

Android版bitchatとPython版`pybitchat`のNoise DMハンドシェイクが完了せず、Python側で次のログが繰り返される場合の切り分け手順。

```text
HS: repeated msg1; restarting responder
HS: resending msg2 len=96
send to ... wire=256
```

Noiseの鍵計算を変更する前に、Pythonのmsg2がAndroidへ届いているか、Android側のどこで処理が止まっているかを確認する。

## 現在のPython側修正

`src/uagent/tools/pybitchat_shared.py` に次の修正を入れている。

1. Noise受信フレームのrecipient IDを自分のPeer IDと照合する。
1. 宛先不一致のNoiseフレームはローカル処理しない。
1. relay判定は宛先チェックより前に行うため、メッシュ転送は維持する。
1. Noise送信時にpayload長、raw長、wire長、recipient IDをログ出力する。

送信ログの形式：

```text
[bitchat] [debug] NOISE TX type=16 recipient=<peer-id> payload=96 raw=<n> wire=256
```

`payload=96`はNoise msg2、`wire=256`はBLE送信用のPKCS#7パディング後の長さを示す。

## 事前準備

1. AndroidとPythonのbitchatを一度停止する。
1. 両方を再起動する。
1. announceが完了し、相手のPeer IDが認識された状態にする。
1. 同時に何度も送らず、DMを1回だけ送る。

同じハンドシェイクを繰り返すと、重複msg1や古いpendingセッションが混ざるため、試験ごとに再起動する。

## Python側ログの確認

Pythonを実行しているターミナルで、次を確認する。

```text
NOISE_HANDSHAKE ... len=32
HS: responder msg1 path
HS: sending msg2 len=96
NOISE TX type=16 recipient=... payload=96 raw=... wire=256
```

または、既存の再送ケースでは次を確認する。

```text
HS: repeated msg1; restarting responder
HS: resending msg2 len=96
NOISE TX type=16 recipient=... payload=96 raw=... wire=256
```

確認項目：

- `payload=96`になっているか
- `wire=256`になっているか
- `recipient`がAndroid自身の8バイトPeer IDか
- `send FAILED`が出ていないか

## Android側ログの確認

### Android Studioを使う場合

Android Studioの**Logcat**を開き、対象端末・対象アプリを選択する。

次のキーワードで絞り込む。

```text
Noise
Handshake
BinaryProtocol
PacketRelayManager
BluetoothPacketBroadcaster
```

### adbを使う場合（Windows PowerShell）

まずログをクリアする。

```powershell
adb logcat -c
```

次に絞り込み表示する。

```powershell
adb logcat -v time | Select-String -Pattern "Noise|Handshake|BinaryProtocol|PacketRelayManager|BluetoothPacketBroadcaster"
```

ファイルに保存する場合：

```powershell
adb logcat -v threadtime > android-bitchat.log
```

この状態でPythonからDMを1回送り、終了後に`Ctrl+C`で停止する。

## Android側で確認するログ

### 1. msg2を受信しているか

次のようなログを探す。

```text
NOISE_HANDSHAKE
len=256
```

または、パディング除去後のpayload長を示すログ。

```text
payload length = 96
```

### 2. 宛先判定で破棄していないか

次の語を探す。

```text
isPacketAddressedToMe
recipient ID
local peer ID
not addressed
```

### 3. Noise処理で失敗していないか

次の語を探す。

```text
processHandshakeMessage
authentication failed
invalid message
handshake exception
```

### 4. msg3を送信しているか

次の語を探す。

```text
msg3
NOISE_HANDSHAKE
writeCharacteristic
BluetoothPacketBroadcaster
```

## 判定表

| 結果 | 推定原因 | 次に確認する場所 |
|---|---|---|
| Androidにmsg2受信ログがない | BLE送信先、GATT書き込み、接続リンク | Pythonの`send FAILED`、AndroidのBluetoothログ |
| msg2受信後にrecipient不一致 | Peer IDまたは宛先IDの不一致 | Pythonの`NOISE TX recipient`とAndroidのlocal Peer ID |
| msg2受信後にauthentication failure | Noise鍵、初期ハッシュ、msg2内容、パディング除去 | AndroidのNoise例外、Pythonのannounce済みNoise公開鍵 |
| msg2処理成功だがmsg3がない | Androidのセッション状態または応答送信処理 | AndroidのNoiseSessionManager、BluetoothPacketBroadcaster |
| Androidがmsg3を送信しているがPythonに届かない | AndroidのBLE書き込みまたはPythonのnotify受信 | Androidの送信ログ、Pythonの`NOISE_HANDSHAKE len=64` |

## 重要な長さ

| メッセージ | Noise payload | BLE wire |
|---|---:|---:|
| msg1 | 32バイト | 通常は256バイトbucket |
| msg2 | 96バイト | 通常は256バイトbucket |
| msg3 | 64バイト | 通常は256バイトbucket |

`wire=256`は異常ではない。Noise msg2本体はパディングを除いた`96`バイトである。

## 今回の優先確認順

1. Pythonの`NOISE TX`ログでrecipient IDを確認する。
1. Android Logcatでmsg2受信ログを探す。
1. Androidが表示するlocal Peer IDとPythonのrecipientを比較する。
1. Androidがmsg2をNoise処理したか確認する。
1. Androidからmsg3が送信されたか確認する。
1. msg3がなければ、Android側の宛先判定またはNoise例外を調べる。

## 関連実装

- Python Noise状態機械：`src/uagent/tools/bitchat_noise.py`
- Python BLE/DM処理：`src/uagent/tools/pybitchat_shared.py`
- iOSの参照実装：`../bitchat/bitchat/Noise/NoiseSessionManager.swift`
- iOSのNoise受信処理：`../bitchat/bitchat/Services/BLE/BLENoisePacketHandler.swift`
- Noiseパディング仕様：`../bitchat/localPackages/BitFoundation/Sources/BitFoundation/MessagePadding.swift`
