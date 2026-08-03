# pybitchat / bitchat 実装監査

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

Noiseの外側フレーム自体は、現行プロトコルどおり署名対象外としている。Noiseのハンドシェイクと暗号化フレームは、TTLを保持したrelay対象として追加した。実機相互接続では、引き続きNoiseのreplay制御と複数hop通信を確認する必要がある。

## 未対応・残課題

主要な明白なバグは対応済みだが、以下は未完了である。

1. **実機相互接続テスト**
   - Android / iOSとの実BLE通信
   - 複数hopのrelay
   - Noiseハンドシェイクの複数hop動作

2. **Noiseの実機replay相互接続確認**
   - 1024件sliding windowは実装済み
   - Android / iOS間で順不同配送と重複nonceを実機確認する必要がある

3. **Fragment再構成の入力検証**
   - 同一転送内で `total_fragments` が変わらないことの検証
   - 総サイズ上限
   - 異常な断片系列の拒否

4. **relayの経路制御**
   - 現在はTTLと受信元除外を備えた簡易フラッディング
   - `../bitchat` の詳細なrelay policyや宛先最適化は未対応

5. **署名鍵の永続的なpinning / TOFU制御**
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
2. Noise DMの平文フォールバック廃止
3. BLE通知ストリーム再構成
4. 実際のmesh relay処理の接続
5. ファイル名衝突時の上書き防止
6. `start()` の二重起動防止
7. BLE起動失敗の状態反映

## テスト状況

以下の既存テストは通過した。

- `tests/test_pybitchat_protocol.py`
- `tests/test_pybitchat_fragment.py`
- `tests/test_pybitchat_noise.py`
- `tests/test_pybitchat_relay.py`
- プロジェクト全体のpytest

ただし、既存テストは主にパケットencode/decode、Noise状態機械、断片再構成、relayクラス単体を対象としている。実際のBLE通知、署名検証、複数peer relay、Android相互接続は十分にカバーしていない。

この監査ではコード変更・修正・コミットは行っていない。
