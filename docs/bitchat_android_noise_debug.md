# bitchat Android Noise DM 相互接続デバッグ手順

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
2. 宛先不一致のNoiseフレームはローカル処理しない。
3. relay判定は宛先チェックより前に行うため、メッシュ転送は維持する。
4. Noise送信時にpayload長、raw長、wire長、recipient IDをログ出力する。

送信ログの形式：

```text
[bitchat] [debug] NOISE TX type=16 recipient=<peer-id> payload=96 raw=<n> wire=256
```

`payload=96`はNoise msg2、`wire=256`はBLE送信用のPKCS#7パディング後の長さを示す。

## 事前準備

1. AndroidとPythonのbitchatを一度停止する。
2. 両方を再起動する。
3. announceが完了し、相手のPeer IDが認識された状態にする。
4. 同時に何度も送らず、DMを1回だけ送る。

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
2. Android Logcatでmsg2受信ログを探す。
3. Androidが表示するlocal Peer IDとPythonのrecipientを比較する。
4. Androidがmsg2をNoise処理したか確認する。
5. Androidからmsg3が送信されたか確認する。
6. msg3がなければ、Android側の宛先判定またはNoise例外を調べる。

## 関連実装

- Python Noise状態機械：`src/uagent/tools/bitchat_noise.py`
- Python BLE/DM処理：`src/uagent/tools/pybitchat_shared.py`
- iOSの参照実装：`../bitchat/bitchat/Noise/NoiseSessionManager.swift`
- iOSのNoise受信処理：`../bitchat/bitchat/Services/BLE/BLENoisePacketHandler.swift`
- Noiseパディング仕様：`../bitchat/localPackages/BitFoundation/Sources/BitFoundation/MessagePadding.swift`
