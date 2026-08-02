# bitchat Android / Python Noise 相互運用調査

## 対象

- Android: `permissionlesstech/bitchat-android`
- 確認コミット: `c02dda308e8a1404d6a6697a4853825723a7413e`
- ローカルclone: `bitchat-android/`
- Python側: `src/uagent/tools/bitchat_noise.py`、`src/uagent/tools/pybitchat_shared.py`

## Android側で確認した仕様

### Noise

- プロトコル名: `Noise_XX_25519_ChaChaPoly_SHA256`
- msg1: 32バイト
- msg2: 80バイト
- msg3: 48バイト
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

`Noise_XX_25519_ChaChaPoly_SHA256` はちょうど32バイトなので、Androidと同じくプロトコル名をそのまま初期値として使用するよう修正した。

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
- msg1/msg2/msg3: `32 / 80 / 48`
- Android側の仕様コードとの照合: 完了

## 現在の未解決点

Android側では、Pythonから256バイトのmsg2を送信した後もmsg1が再送され、msg3が返らない場合がある。

このため、残る確認対象はAndroid端末上の実行時処理である。

- `BinaryProtocol.decode` の実際の結果
- `PacketRelayManager.isPacketAddressedToMe` のrecipient ID判定
- `NoiseSessionManager.processHandshakeMessageWithResult` の例外
- `BluetoothPacketBroadcaster` / GATT送信経路でのmsg2受信状況

GitHubコードから仕様は確認できるが、Androidが実行時にmsg2を拒否した直接の理由は端末ログがないと確定できない。
