# IOT_USECASE（日本語版）

`tool_genre: "iot"` のツールを、`uag` からどう使うかをまとめる。

この文書は、IoT / LAN 機器 / BLE / クラウド連携機器を扱うときの共通ガイドであり、まず何を使うか、どの順で使うか、失敗したら何を見るかを整理する。

## 目的

- LAN 内や近距離の機器を一覧する
- 対象機器の状態を読む
- 必要に応じて制御する
- JSON を中心に、機械処理しやすい形で扱う
- 失敗理由を短く把握し、次の切り分けに進める

## 対象ツール群

`tool_genre: "iot"` の主な対象は次のとおり。

### BLE

- `ble_ops`
- `switchbot_ble_scan`
- `switchbot_ble_status`
- `switchbot_ble_control`

### SwitchBot Cloud

- `switchbot_cloud_list`
- `switchbot_cloud_status`
- `switchbot_cloud_control`

### ECHONET Lite

- `echonet_scan`
- `echonet_node_status`
- `echonet_object_list`
- `echonet_property_list`
- `echonet_property_get`
- `echonet_property_set`
- `echonet_control`
- `echonet_monitor`
- `echonet_cache`

### UPnP

- `upnp_scan`
- `upnp_igd_control`

### Matter

- `matter_controller_list`
- `matter_bridge_list`
- `matter_device_status`
- `matter_endpoint_list`
- `matter_cluster_list`

## 共通方針

### 1. まずは一覧・状態確認から始める

IoT 系は、いきなり制御するよりも、まず対象を正しく特定するのが重要。

基本順序:

1. 探索 / 一覧
2. 状態確認
3. 必要に応じて詳細取得
4. 必要に応じて制御

### 2. JSON を基本にする

- 自動処理や後続ツール連携では `json`
- 人間が見やすい簡易確認だけ `text`
- 迷ったら `json`

### 3. 対象を一意にする

制御や詳細取得では、対象が曖昧だと失敗しやすい。

よく使う識別子:

- BLE: `address`, `char_uuid`
- SwitchBot: `device_id`, `device_name`
- ECHONET Lite: `ip_address`, `eoj`, `object_code`, `epc`
- UPnP: `interface`, `search_target`, `location`, `usn`
- Matter: `controller_id`, `bridge_id`, `device_id`, `endpoint`, `cluster`

### 4. 取得できない項目は null か省略

ツール間で扱いを揃える。

- 取れない情報は `null`
- 存在しない情報は省略
- 同じ意味のキーは増やしすぎない

### 5. 失敗は短く返す

代表的な失敗理由:

- `config_missing`
- `not_found`
- `ambiguous_target`
- `network_error`
- `timeout`
- `unsupported_device`
- `invalid_argument`

### 6. 秘密情報を残さない

- トークンやシークレットはログや長期記憶に保存しない
- 環境変数を使う場合は `UAGENT_` 接頭辞に統一する

## 使い分けの基本

### BLE

近距離の Bluetooth Low Energy 機器を扱う。

向いているもの:

- 近くにある機器の探索
- GATT の読み取り / 書き込み
- SwitchBot の BLE 系機器

注意点:

- 距離と電波状況の影響を受けやすい
- Windows / Linux / macOS でアドレスの扱いが少し違う
- 権限不足や Bluetooth スタックの状態で失敗することがある

代表的な流れ:

1. `ble_ops` で探索
2. `switchbot_ble_status` で対象確認
3. `switchbot_ble_control` で制御

### SwitchBot Cloud

クラウド経由で SwitchBot 機器を扱う。

向いているもの:

- アカウントに紐づいたデバイス一覧
- デバイス状態の確認
- 離れた場所からの制御

注意点:

- 認証情報が必要
- ネットワーク経由なのでローカル BLE より安定しやすい
- ただしクラウド側の API 制限や応答失敗はありうる

必要な認証情報:

- `UAGENT_SWITCHBOT_TOKEN`
- `UAGENT_SWITCHBOT_SECRET`

代表的な流れ:

1. `switchbot_cloud_list` で一覧を確認
2. `switchbot_cloud_status` で対象の状態を見る
3. `switchbot_cloud_control` で操作する

### ECHONET Lite

LAN 内の ECHONET Lite 機器を扱う。

向いているもの:

- 家電ノード探索
- ノードやオブジェクトの状態取得
- EPC 単位の読み書き
- 監視による変化追跡

注意点:

- multicast が通らないと探索できないことがある
- ルータや OS のネットワーク設定に影響される
- `ip_address` / `interface` の指定が重要になることがある

代表的な流れ:

1. `echonet_scan` で LAN 内ノードを探す
2. `echonet_node_status` でノード状態を確認する
3. `echonet_object_list` / `echonet_property_list` / `echonet_property_get` で詳細を見る
4. `echonet_property_set` / `echonet_control` で制御する
5. `echonet_monitor` で変化を追う
6. `echonet_cache` で探索結果や状態キャッシュを確認する

制御時の考え方:

- まず対象種類を確認する
- その機器に対応した操作だけを選ぶ
- 失敗したら `unsupported_device` や `unsupported_property` を見る

### UPnP

LAN 内の UPnP / SSDP 機器や IGD ルータを扱う。

向いているもの:

- ルータやメディア機器の探索
- UPnP で公開されている機器情報の確認
- IGD のポートマッピング確認 / 操作

注意点:

- UPnP 自体が無効化されている場合がある
- SSDP multicast が通らないと見つからない
- ルータ実装によって応答の差がある

代表的な流れ:

1. `upnp_scan` で機器を探す
2. `upnp_igd_control` で IGD 機能を確認 / 操作する

### Matter

Matter 連携機器を扱う。

向いているもの:

- controller / bridge / device の構造確認
- 管理下デバイスの一覧
- device の状態確認
- endpoint / cluster の確認

注意点:

- Matter は階層があるため、controller / bridge / device を分けて考える
- 現時点では読み取り系が中心
- 制御は将来拡張の対象

代表的な流れ:

1. `matter_controller_list` でコントローラーを確認
2. `matter_bridge_list` でブリッジを確認
3. `matter_device_status` で対象デバイスの状態を確認
4. 必要に応じて `matter_endpoint_list` / `matter_cluster_list` で構成を見る

## 実践フロー

### A. 何が見えるかを知りたい

まずは探索系を使う。

- BLE: `ble_ops` / `switchbot_ble_scan`
- ECHONET Lite: `echonet_scan`
- UPnP: `upnp_scan`
- Matter: `matter_controller_list` / `matter_bridge_list`
- SwitchBot Cloud: `switchbot_cloud_list`

### B. 対象の状態を知りたい

一覧のあと、状態取得系を使う。

- BLE: `switchbot_ble_status`
- SwitchBot Cloud: `switchbot_cloud_status`
- ECHONET Lite: `echonet_node_status`
- Matter: `matter_device_status`

### C. 詳細を掘りたい

より細かい構造を確認する。

- ECHONET Lite: `echonet_object_list`, `echonet_property_list`, `echonet_property_get`
- Matter: `matter_endpoint_list`, `matter_cluster_list`
- UPnP: `upnp_igd_control` の結果確認

### D. 制御したい

対象が一意で、対応操作が分かっているときだけ行う。

- BLE: `switchbot_ble_control`
- SwitchBot Cloud: `switchbot_cloud_control`
- ECHONET Lite: `echonet_property_set`, `echonet_control`
- UPnP: `upnp_igd_control`

Matter は現時点では主に読み取り系を使う。
制御は将来の拡張対象として扱う。

## `output_format` の使い分け

### `json`

- 解析や自動処理向け
- 他ツールに渡す前提のとき
- ログや記録に残すとき

### `text`

- 画面でざっと見るとき
- 人間が確認するだけのとき
- エラー内容を短く見たいとき

原則:

- スクリプト利用は `json`
- 目視確認だけなら `text`

## ツールごとの使い方メモ

### `ble_ops`

- BLE の汎用探索 / 読み書き
- `scan`, `read`, `write` を扱う
- `scan_mode` で BLE のみか Classic も含めるかを選ぶ

よくある使い方:

- 近くのデバイスを探す
- 既知のアドレスに接続して GATT を読む
- 値を書き込む

### `switchbot_ble_*`

- SwitchBot の BLE 機器向け
- 探索、状態確認、操作の 3 段階で使う

### `switchbot_cloud_*`

- SwitchBot Cloud API 向け
- 一覧、状態、制御の順で使う
- 認証情報がないと使えない

### `echonet_*`

- LAN 内の ECHONET Lite 機器向け
- 探索 → 状態 → 詳細 → 制御 → 監視 の順で使う
- multicast や interface の問題に注意する

### `upnp_*`

- UPnP / SSDP 機器向け
- 探索してから IGD を扱う
- ルータの UPnP 設定に依存する

### `matter_*`

- Matter の controller / bridge / device を分けて扱う
- まず一覧、次に状態、必要なら endpoint / cluster を見る
- 現時点では読み取り中心

## よくある失敗と見方

### 1. 見つからない

- `not_found`
- 対象 ID が違う
- 対象がネットワーク上に見えない

### 2. 曖昧

- `ambiguous_target`
- `device_id` だけでは足りない
- `controller_id` / `bridge_id` / `endpoint` の補助が必要

### 3. 設定不足

- `config_missing`
- 認証情報不足
- 環境変数未設定

### 4. 通信できない

- `network_error`
- `timeout`
- BLE 権限不足
- multicast / UDP が通らない

### 5. 対応していない

- `unsupported_device`
- `unsupported_property`
- その機器や機能はまだ対象外

## 運用上の注意

- 対象を曖昧なまま制御しない
- まず一覧と状態確認を挟む
- 一度失敗したら、ID / interface / 認証情報 / ネットワークを切り分ける
- ログや記録に秘密情報を残さない
- `text` は見やすいが、後で処理するなら `json` を残す

## 代表的な環境変数

### SwitchBot

- `UAGENT_SWITCHBOT_TOKEN`
- `UAGENT_SWITCHBOT_SECRET`

### Matter

- 必要に応じて `UAGENT_MATTER_...` 系で統一する

### ECHONET Lite / UPnP

- 必要に応じて `UAGENT_` 接頭辞で統一する
- 秘密情報をログに出さない
