# OKOK / Chipsea BLE 体重計データ取得ツール 設計書

| 項目 | 内容 |
|---|---|
| 文書種別 | 実装用設計書 |
| 対象 | OKOK International / Chipsea-BLE 系体重計（C0 広告型） |
| 版 | 1.0 |
| 目的 | 体重データの取得・確定・保存を行うツールの実装指針 |
| 非目的 | 体脂肪など体組成17項目の算出、ScaleFit 互換、クラウド連携 |

---

## 1. 概要

### 1.1 背景

対象体重計は Bluetooth Low Energy (BLE) の **広告パケット (Advertisement / Manufacturer Specific Data)** に体重を載せてブロードキャストする。ペアリングや GATT 接続は不要。

実機で確認済みの系統:

- デバイス名: 空、または `Chipsea-BLE` 等
- 広告タイプ: Manufacturer Specific Data
- 代表フレーム例（安定時）:

```text
02 fc 17 70 0a 01 21 a8 0b 6b ed 6b f1
```

- `02 FC` → big-endian `0x02FC` = 764 → **76.4 kg**

### 1.2 ゴール

1. BLE 広告を受信する
2. 対象スケールのフレームを識別・パースする
3. 測定中の揺れを除外し、**確定体重**を得る
4. ローカルに記録する（CSV / JSONL）
5. 将来の拡張（複数機種、インピーダンス）に耐える構造にする

### 1.3 非ゴール（本実装ではやらない）

- 体脂肪率・筋肉量などの体組成計算
- ScaleFit / OKOK アプリとの通信互換
- クラウド送信、Google Sheets 連携
- GUI
- ユーザー識別（複数人の自動判別）
- Windows 以外 OS の一次対応（設計上は移植可能にする）

---

## 2. 前提・制約

### 2.1 実行環境

| 項目 | 想定 |
|---|---|
| OS | Windows 10/11（一次） |
| 言語 | Python 3.11+ |
| BLE | ホスト PC の Bluetooth アダプタ |
| ライブラリ | `bleak`（スキャン） |
| 権限 | Bluetooth 利用可、管理者権限は原則不要 |

### 2.2 デバイス前提

- スケールは測定時に広告を出す
- 電源 OFF / スリープ中は広告が止まることがある
- 接続不要（passive scan で足りる）
- 同一空間に複数の類似デバイスがある可能性あり

### 2.3 既知のプロトコル制約

| 項目 | 内容 |
|---|---|
| 公開情報で確実な値 | 体重 (kg) |
| 安定判定 | フラグバイト、または値の時間的安定 |
| 体組成 | C0 系統は広告に含まれない公算が大きい |
| 単位 | 実測・公開情報上は kg 固定のことが多い |
| 機種差 | V20 / V11 / VF0 / C0 などでペイロード長・会社 ID が異なる |

---

## 3. プロトコル仕様（実装対象）

### 3.1 対象プロファイル: OKOK C0 広告型

本ツールの **第一実装対象** は、実機で確認した C0 系 13 バイト前後の Manufacturer Data。

#### 3.1.1 ペイロード構造（実測ベース）

| オフセット | 長さ | 内容 | 備考 |
|---|---|---|---|
| 0 | 2 | 体重 raw | big-endian uint16。`raw / 10.0` = kg |
| 2 | 4 | 固定っぽい領域 | 例: `17 70 0A 01`。機種・状態で変化しうる。体重判定には使わない |
| 6 | 1 | 状態フラグ候補 | 安定/測定中のヒント。機種差あり |
| 7 | 6 | MAC らしき領域 | デバイス識別の補助 |
| 以降 | 可変 | 予備 / チェックサム等 | 機種依存。未知なら無視 |

#### 3.1.2 体重デコード

```text
weight_kg = int.from_bytes(payload[0:2], "big") / 10.0
```

例:

| hex | decimal | kg |
|---|---|---|
| `02 FC` | 764 | 76.4 |
| `00 00` | 0 | 0.0（空/ゼロ） |

#### 3.1.3 安定判定（二段構え）

公開情報と実測のばらつきを吸収するため、次の優先順位で確定する。

1. **フラグベース（取れる場合）**
   - 状態バイトが「安定」を示す値なら候補をロック
   - ただし機種差が大きいため、単独依存しない
2. **時間安定ベース（必須フォールバック）**
   - 同一体重（許容誤差内）が `lock_seconds` 継続したら確定
3. **セッション終了ベース**
   - 広告が `session_timeout_s` 途切れたら、直近の安定候補を確定

#### 3.1.4 フィルタ条件

受信フレームを採用する条件:

1. Manufacturer Specific Data が存在する
2. ペイロード長が最小長以上（C0: 最低 7 バイト推奨、理想 13）
3. 体重 raw が妥当範囲（例: 0.0〜300.0 kg）
4. （任意）MAC / アドレスが許可リストに一致
5. （任意）既知の固定バイトパターンに部分一致

> 注意: Company ID や先頭マジックは機種で異なる。  
> **厳密一致だけで落とすと取りこぼす**ため、設定で緩くできるようにする。

### 3.2 将来拡張用プロファイル（実装はスタブでよい）

| プロファイル | 特徴 | 本版 |
|---|---|---|
| OKOK V20 (`0x20CA` 等) | 体重 + impedance の可能性 | パーサ IF のみ予約 |
| Chipsea `0xA0CA` lb 系 | lb 単位、別ヘッダ | 未実装 |
| openScale OkOk 系 | 複数サブタイプ | 参照情報のみ |

---

## 4. システム構成

### 4.1 論理構成

```text
┌─────────────────────────────────────────────┐
│                 CLI Entrypoint              │
│            (scale_tool.py 等)               │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│                 App Service                 │
│  - 設定読込                                 │
│  - ライフサイクル管理                         │
│  - シグナル/終了処理                          │
└───────┬─────────────────────────┬───────────┘
        │                         │
        ▼                         ▼
┌───────────────────┐   ┌─────────────────────┐
│   BleScanner      │   │  SessionManager     │
│  - bleak scan     │──▶│  - 測定セッション    │
│  - adv callback   │   │  - 安定判定         │
└───────────────────┘   │  - 重複排除         │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │     Parsers         │
                        │  - C0Parser         │
                        │  - (V20Parser...)   │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │     Exporters       │
                        │  - CsvExporter      │
                        │  - JsonlExporter    │
                        │  - ConsoleExporter  │
                        └─────────────────────┘
```

### 4.2 データフロー

```text
BLE Advertisement
  → 生バイト抽出
  → Parser 選択 / デコード
  → WeightSample 生成
  → SessionManager が測定中サンプルを集約
  → 安定条件を満たしたら WeightReading を確定
  → Exporter が永続化 + コンソール表示
```

### 4.3 プロセスモデル

- 単一プロセス
- asyncio ベース
- スキャンは常時（または測定検知後の短時間強化でも可）
- 永続化は確定時のみ（生ログは任意）

---

## 5. モジュール設計

### 5.1 ディレクトリ構成（案）

```text
scale_tool/
  README.md
  pyproject.toml          # または requirements.txt
  design.md               # 本設計書
  src/
    scale_tool/
      __init__.py
      __main__.py
      cli.py
      config.py
      models.py
      scanner.py
      session.py
      parsers/
        __init__.py
        base.py
        c0.py
      exporters/
        __init__.py
        base.py
        csv_exporter.py
        jsonl_exporter.py
        console.py
      util/
        logging.py
        timeutil.py
  tests/
    test_c0_parser.py
    test_session.py
  data/                   # 実行時出力先（gitignore 推奨）
```

### 5.2 責務分割

| モジュール | 責務 | やってはいけないこと |
|---|---|---|
| `cli.py` | 引数解析、起動 | プロトコル解釈 |
| `config.py` | 設定の読込・検証 | I/O 本体 |
| `scanner.py` | BLE 受信、コールバック配送 | 体重確定ロジック |
| `parsers/*` | バイト列 → サンプル | ファイル保存 |
| `session.py` | 安定判定・セッション管理 | BLE API 直接操作 |
| `exporters/*` | 出力 | パース |
| `models.py` | データ構造 | 副作用 |

---

## 6. データモデル

### 6.1 WeightSample（未確定の生サンプル）

```python
@dataclass(frozen=True)
class WeightSample:
    timestamp: datetime          # timezone-aware UTC 推奨
    address: str                 # BLE address
    rssi: int | None
    weight_kg: float
    stable_hint: bool | None     # パーサが読めた場合のみ
    raw_payload_hex: str
    parser_id: str               # 例: "okok_c0"
    company_id: int | None
```

### 6.2 WeightReading（確定レコード）

```python
@dataclass(frozen=True)
class WeightReading:
    reading_id: str              # uuid4
    determined_at: datetime
    address: str
    weight_kg: float
    sample_count: int            # 確定に使ったサンプル数
    duration_ms: int             # セッション長
    method: str                  # "flag" | "lock_window" | "timeout"
    raw_payload_hex: str         # 代表フレーム
    parser_id: str
```

### 6.3 出力スキーマ（CSV）

ヘッダ固定:

```text
reading_id,determined_at_iso,address,weight_kg,sample_count,duration_ms,method,parser_id,raw_payload_hex
```

### 6.4 出力スキーマ（JSONL）

1 行 1 レコード:

```json
{
  "reading_id": "…",
  "determined_at": "2026-03-22T12:34:56.789Z",
  "address": "AA:BB:CC:DD:EE:FF",
  "weight_kg": 76.4,
  "sample_count": 12,
  "duration_ms": 2300,
  "method": "lock_window",
  "parser_id": "okok_c0",
  "raw_payload_hex": "02fc17700a0121a80b6bed6bf1"
}
```

---

## 7. 主要アルゴリズム

### 7.1 スキャンコールバック

```text
on_advertisement(device, adv):
  for company_id, payload in adv.manufacturer_data:
    sample = try_parse(device.address, adv.rssi, company_id, payload)
    if sample is not None:
      session_manager.accept(sample)
```

### 7.2 パーサ選択

```text
try_parse(...):
  for parser in enabled_parsers:  # 優先度順
    sample = parser.parse(...)
    if sample is not None:
      return sample
  return None
```

C0 パーサの受理条件（初期値）:

1. `len(payload) >= 7`
2. `0 <= weight_kg <= 300`
3. 設定で `address_allowlist` がある場合は一致必須
4. 設定で `payload_contains` がある場合は部分一致

### 7.3 セッション管理

状態:

```text
IDLE → TRACKING → DETERMINED → IDLE
```

#### IDLE

- 有効サンプル（例: weight > 0）を受けたら TRACKING 開始

#### TRACKING

保持する情報:

- `session_id`
- `address`
- `first_seen`
- `last_seen`
- `samples[]`（または直近 N 件）
- `candidate_weight`
- `candidate_since`

更新規則:

1. アドレスが違うサンプルは別セッション（同時は第一版非対応でも可）
2. `weight == 0` が続いたら「降りた」とみなし、候補があれば確定して IDLE
3. `abs(weight - candidate) <= epsilon` なら継続、超えたら候補をリセット
4. 候補が `lock_seconds` 以上継続 → DETERMINED
5. `now - last_seen > session_timeout_s` → 候補があれば確定、なければ破棄

#### DETERMINED

- `WeightReading` を生成
- exporter へ渡す
- 同一体重の連続確定を防ぐため、クールダウン `dedupe_seconds` を入れる
- IDLE へ戻る

### 7.4 デフォルトパラメータ

| 名前 | 初期値 | 意味 |
|---|---|---|
| `lock_seconds` | 1.5 | 同一体重の継続で確定 |
| `session_timeout_s` | 8.0 | 広告途切れで確定/終了 |
| `epsilon_kg` | 0.05 | 同一視する体重差 |
| `min_weight_kg` | 5.0 | これ未満は無視（ペット/物置き対策は任意） |
| `max_weight_kg` | 300.0 | 上限 |
| `dedupe_seconds` | 30.0 | 同一確定の再出力抑制 |
| `raw_log_enabled` | false | 全サンプルの生ログ |

`min_weight_kg` は 0 許容モードも設定可能にする（キャリブレーション観察用）。

---

## 8. CLI 設計

### 8.1 コマンド

```text
python -m scale_tool scan [options]
python -m scale_tool once [options]
python -m scale_tool parse-hex <hex> [options]
```

| サブコマンド | 用途 |
|---|---|
| `scan` | 常時監視して確定体重を記録 |
| `once` | 最初の 1 件確定で終了 |
| `parse-hex` | 保存済みペイロードのオフライン検証 |

### 8.2 主要オプション

```text
--address AA:BB:CC:DD:EE:FF     # 対象固定（推奨）
--csv path\weights.csv          # CSV 出力
--jsonl path\weights.jsonl      # JSONL 出力
--lock-seconds 1.5
--session-timeout 8.0
--min-weight 5.0
--raw-log path\raw.jsonl        # 任意
--parser c0                     # 将来複数
--adapter default               # bleak adapter
--verbose
```

### 8.3 終了コード

| code | 意味 |
|---|---|
| 0 | 正常 |
| 1 | 一般エラー |
| 2 | 引数/設定エラー |
| 3 | Bluetooth 初期化/スキャン失敗 |
| 4 | `once` がタイムアウトで 0 件 |

---

## 9. 設定

### 9.1 優先順位

1. CLI 引数
2. 環境変数（必要最小限）
3. 設定ファイル（任意: `scale_tool.toml`）
4. デフォルト値

### 9.2 設定ファイル例

```toml
[device]
address = "AA:BB:CC:DD:EE:FF"

[parse]
parser = "c0"
min_weight_kg = 5.0
max_weight_kg = 300.0
epsilon_kg = 0.05

[session]
lock_seconds = 1.5
session_timeout_s = 8.0
dedupe_seconds = 30.0

[output]
csv = "data/weights.csv"
jsonl = "data/weights.jsonl"
console = true

[log]
level = "INFO"
raw_log = ""
```

---

## 10. エラー処理・信頼性

### 10.1 方針

- **ローカル確定ログを Source of Truth** とする
- 表示や将来の外部送信失敗で本体を止めない
- Bluetooth スタックエラー時はバックオフ再起動

### 10.2 再起動ポリシー

```text
scan loop:
  try start scanner
  on BleakError / OSError:
    log error
    stop scanner safely
    sleep backoff (5s, 上限 60s)
    retry
```

### 10.3 永続化の信頼性

- CSV/JSONL は 1 レコード書くたびに `flush`
- 可能なら `fsync`（Windows でも有効な範囲で実施）
- 書き込み失敗はエラーログし、スキャンは継続

### 10.4 時刻

- 内部は UTC aware datetime
- 出力 ISO 8601（`...Z`）
- ローカル時刻が必要なら表示層のみ変換

---

## 11. ロギング

| レベル | 出すもの |
|---|---|
| DEBUG | 全受信ペイロード、パース失敗理由 |
| INFO | スキャン開始/停止、確定体重 |
| WARNING | 想定外ペイロード長、連続パース失敗 |
| ERROR | Bluetooth 障害、ファイル I/O 失敗 |

コンソール表示例:

```text
2026-03-22 12:34:56 INFO  scan started
2026-03-22 12:35:10 INFO  tracking AA:BB:CC:DD:EE:FF weight=76.2
2026-03-22 12:35:12 INFO  determined 76.4 kg (lock_window, samples=14)
```

---

## 12. テスト設計

### 12.1 単体テスト（必須）

| 対象 | ケース |
|---|---|
| C0Parser | 正常系 `02FC...` → 76.4 |
| C0Parser | 短すぎるペイロード → None |
| C0Parser | 範囲外体重 → None |
| SessionManager | 安定継続で確定 |
| SessionManager | 値変動で候補リセット |
| SessionManager | タイムアウト確定 |
| SessionManager | ゼロ連続でセッション終了 |
| SessionManager | dedupe で二重確定防止 |

### 12.2 オフライン回帰

`parse-hex` と fixtures を使い、実機キャプチャ hex をテストデータ化:

```text
tests/fixtures/c0_stable_764.txt
tests/fixtures/c0_zero.txt
tests/fixtures/c0_measuring_seq.json
```

### 12.3 実機テスト（手動）

1. スケールに乗る
2. 表示が安定
3. ツールが 1 回だけ近い値で確定
4. 降りる
5. 再測定で次の 1 回が記録される

---

## 13. 実装タスク分解

### Phase 0: 骨組み

- [ ] パッケージ構成作成
- [ ] `models.py` / `config.py` / logging
- [ ] CLI スケルトン

### Phase 1: パーサ

- [ ] `parsers/base.py` インターフェース
- [ ] `parsers/c0.py` 実装
- [ ] `parse-hex` サブコマンド
- [ ] 単体テスト

### Phase 2: セッション

- [ ] `session.py` 状態機械
- [ ] 確定ロジックと dedupe
- [ ] 単体テスト

### Phase 3: スキャナ接続

- [ ] `scanner.py` + bleak
- [ ] `scan` / `once`
- [ ] Bluetooth エラー再起動

### Phase 4: 出力

- [ ] Console / CSV / JSONL exporter
- [ ] flush/fsync
- [ ] 手動実機確認

### Phase 5: 仕上げ

- [ ] README（使い方のみ）
- [ ] 設定ファイル対応
- [ ] 失敗時メッセージの整理

---

## 14. インターフェース定義（実装時の型）

### 14.1 Parser IF

```python
class ScaleParser(Protocol):
    parser_id: str

    def parse(
        self,
        *,
        address: str,
        rssi: int | None,
        company_id: int | None,
        payload: bytes,
        timestamp: datetime,
    ) -> WeightSample | None:
        ...
```

### 14.2 Exporter IF

```python
class ReadingExporter(Protocol):
    def emit(self, reading: WeightReading) -> None:
        ...

    def close(self) -> None:
        ...
```

### 14.3 Session IF

```python
class SessionManager:
    def accept(self, sample: WeightSample) -> WeightReading | None:
        """サンプルを投入し、確定時のみ Reading を返す。"""
        ...

    def tick(self, now: datetime) -> WeightReading | None:
        """タイムアウト判定用。スキャナの watchdog から呼ぶ。"""
        ...
```

---

## 15. セキュリティ / プライバシー

- 体重は機微な健康データとして扱う
- デフォルト出力はローカルファイルのみ
- ログに氏名など個人識別子を入れない
- raw payload に MAC が含まれるため、共有前に必要ならマスクする
- 本設計範囲にネットワーク送信を含めない

---

## 16. 既知の制限事項

1. **体組成は取得しない**（C0 広告に無い前提）
2. 複数人が連続で乗った場合の自動識別はしない
3. 同時複数スケールは第一版では allowlist で 1 台推奨
4. 会社 ID / フラグ意味は機種差があり、厳密仕様ではない
5. スケールが広告を出さない時間帯は取得不能
6. Windows の Bluetooth スタック不調時は再起動が必要になる場合あり

---

## 17. 受け入れ条件（Done の定義）

以下を満たせば実装完了とする。

1. 実機測定で安定体重が **1 回の測定につき 1 レコード** 記録される
2. 記録値はスケール表示と概ね一致（±0.1 kg 目安）
3. CSV または JSONL に追記される
4. スキャン中に Bluetooth エラーが起きても自動復帰を試みる
5. `parse-hex` で既知ペイロードが正しく kg 変換される
6. 体組成や外部 API に依存しない

---

## 18. 実装時の優先判断ルール

迷ったときの原則:

1. **取りこぼしより誤確定を避ける**（ただし timeout で閉じる）
2. **パーサを厚くせず、session で吸収**する
3. 機種固有値はハードコードしすぎず設定へ
4. 動かない最適化・抽象化を増やさない
5. まず C0 体重のみを確実に通す

---

## 19. 参考情報（実装参照用）

| 種別 | 内容 |
|---|---|
| 実測 | `02 fc 17 70 0a 01 21 ...` → 76.4 kg |
| openScale | OkOkHandler（V20 は impedance、C0 は体重中心） |
| HA | homeassistant-okokscale（体重中心） |
| 類似実装 | bleak による advertisement scan + manufacturer_data 解析 |

> 参考実装をコピーする場合も、ライセンスを確認すること。

---

## 20. 当面の実装スコープ宣言

**この設計書に基づく第一版で実装するもの**

- OKOK C0 系広告からの体重取得
- 安定確定
- コンソール表示
- CSV/JSONL 保存
- オフライン hex パース

**第一版で実装しないもの**

- 体脂肪・インピーダンス
- GUI
- クラウド
- 自動ユーザー識別
- 複数プロファイルの完全対応

---

## 付録 A. 状態遷移図

```text
                 weight>0
      ┌────────── sample ──────────┐
      │                            ▼
    IDLE                       TRACKING
      ▲                            │
      │                   ┌────────┼────────┐
      │                   │        │        │
      │              lock_window  flag   timeout/zero
      │                   │        │        │
      │                   ▼        ▼        ▼
      │                     DETERMINED
      │                          │
      └──────── emit + dedupe ───┘
```

## 付録 B. 最小シーケンス

```text
User steps on scale
  → advertisements stream (varying kg)
  → Session TRACKING
  → values settle at 76.4 for >= lock_seconds
  → WeightReading(76.4)
  → CSV append
User steps off
  → zero/idle or silence
  → IDLE
```

## 付録 C. 依存パッケージ（第一版）

```text
bleak>=0.22
```

開発用:

```text
pytest>=8.0
```

---

以上を実装の単一ソースとする。実装中にプロトコルの新事実が判明した場合は、本設計書の「3. プロトコル仕様」と「16. 既知の制限事項」を先に更新してからコードを変更する。
