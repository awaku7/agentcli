# SPEC: cl2idx / dds2idx

IBM i（AS/400）周辺ソース向け `*2idx` ツール仕様。

- 状態: **Implemented（v1 + v2 + REF follow + DSPF indicator/attr decode）**
- 作成日: 2026-03-22
- 関連: `cobol2idx`, `DEVELOP.md`（`*2idx` 節）, `DEVELOP_TOOL.md`
- 方針: **`cobol2idx` には統合しない**。言語ごとに独立ツールとする。

______________________________________________________________________

## 1. 背景と目的

### 1.1 現状

| ツール | 対象 | 状態 |
|--------|------|------|
| `cobol2idx` | `.cbl` / `.cob` / `.cpy` | 実装済み |
| `cl2idx` | `.cl` / `.clp` / `.clle` 等 | **実装済み** |
| `dds2idx` | `.pf` / `.lf` / `.dspf` / `.prtf` / `.dds` 等 | **実装済み**（REF follow + DSPF indicator/attr/const） |

`cobol2idx` は COBOL の division / section / paragraph / data 等を正規表現で索引化する。
CL・DDS は文法も構造単位も異なるため、同一ツールへの機能追加は行わない。

### 1.2 目的

大きな CL / DDS ソースを全文読込せずに:

1. `mode="index"` で番号付き目次を取得する
2. `mode="section"` で必要な定義ブロックだけ取得する

ことで、LLM のトークン消費を抑えつつ構造把握を可能にする。

### 1.3 非目的

- 完全な構文解析・意味解析・コンパイル互換パーサにはしない
- 実行・コンパイル・IBM i への接続は行わない
- RPG / RPGLE は本仕様の対象外 → 別ツール `rpg2idx` として実装済み

______________________________________________________________________

## 2. 設計方針

### 2.1 既存 `*2idx` との一貫性

全 `*2idx` と同一インターフェース:

```
cl2idx(path="...", mode="index")
cl2idx(path="...", mode="section", section=N)

dds2idx(path="...", mode="index")
dds2idx(path="...", mode="section", section=N)
```

共通要件:

| 項目 | 内容 |
|------|------|
| genre | `index` |
| 依存 | stdlib のみ（`index_tool_helpers` 再利用） |
| パス解決 | `resolve_index_path` |
| 読込 | `read_index_source` |
| i18n | `make_tool_translator(__file__)` + `*_tool.json` |
| 並列 | `x_parallel_safe: True` |
| 外部依存 | なし |

### 2.2 分離理由

| | COBOL | CL | DDS |
|---|---|---|---|
| 役割 | 業務ロジック | ジョブ／制御 | DB・画面・帳票定義 |
| 構造単位 | division / section / paragraph | PGM / DCL / コマンド / ラベル | レコード / 項目 / キー |
| 表記 | 文＋ピリオド | コマンド＋キーワード | 固定列スペック |
| 拡張子 | `.cbl` `.cob` `.cpy` | `.cl` `.clp` `.clle` | `.pf` `.lf` `.dspf` `.prtf` `.dds` |

混在させると:

1. パーサ分岐が肥大化する
2. `TOOL_SPEC` 説明が曖昧になり LLM が誤用しやすい
3. COBOL 既存パターンに副作用が出る
4. 他 `*2idx` の「1言語1ツール」方針と矛盾する

### 2.3 配置ファイル（予定）

```
src/uagent/tools/cl2idx_tool.py
src/uagent/tools/cl2idx_tool.json
src/uagent/tools/dds2idx_tool.py
src/uagent/tools/dds2idx_tool.json
```

ドキュメント更新箇所:

- `src/uagent/docs/DEVELOP.md`（`*2idx` 表）
- `src/uagent/docs/DEVELOP.ja.md`（同）

______________________________________________________________________

## 3. 共通インターフェース

### 3.1 パラメータ

| 名前 | 型 | 必須 | 説明 |
|------|----|------|------|
| `path` | string | yes | 対象ファイルパス |
| `mode` | string enum: `index` \| `section` | yes | 動作モード |
| `section` | integer | mode=section 時必須 | 目次の番号（1始まり） |

### 3.2 出力

#### mode=index

```
Index for: {path}
---
  1. L12 ...
  2. L40 ...
      3. L45 ...
---
Total definitions: {total}
To retrieve a definition, call {tool} with mode='section' and the section number.
```

- 番号はフラット連番（ネスト表示でも番号は通し）
- 各行に開始行 `L{n}` を付与
- 子要素はインデント（既存 `cobol2idx` と同様）

#### mode=section

- 該当エントリの `line` 〜 `end_line` のソースをそのまま返す
- 末尾の空行は除去
- 範囲外はエラー（`Valid range: 1..{last}`）

### 3.3 エラーメッセージ（既存 idx と揃える）

| 条件 | メッセージ方針 |
|------|----------------|
| path 欠落 | `'path' is required` |
| ファイルなし | `File not found: {path}` |
| 読込失敗 | `Error reading file: {e}` |
| 解析失敗 | `Error parsing file: {e}` |
| section 欠落 | `'section' required when mode='section'` |
| section 非整数 | `'section' must be an integer` |
| section 範囲外 | `Section N not found. Valid range: 1..M` |
| mode 不正 | `Invalid mode. Use 'index' or 'section'` |
| 定義なし | index 時 `(no definitions found)` |

### 3.4 end_line の決め方

既存 `cobol2idx` と同じ:

1. トップレベルエントリは「次の同レベル開始行 − 1」まで
2. 最後のエントリは EOF まで
3. 子メンバーも「次の兄弟 − 1」、最後は親の end_line

______________________________________________________________________

## 4. cl2idx 仕様

### 4.1 対象ファイル

| 拡張子 | 内容 |
|--------|------|
| `.cl` | CL ソース（汎用） |
| `.clp` | CL Program |
| `.clle` | ILE CL |
| `.txt` 等 | 拡張子は強制しない。内容が CL なら解析を試みる |

拡張子チェックは警告レベルに留め、解析自体は実行する（`cobol2idx` と同様、厳密拒否しない）。

### 4.2 前処理

- 大文字小文字は区別しない（照合は upper 正規化）
- 行コメント:
  - 先頭 `/* ... */`（同一行）
  - 全行がコメントのみの場合はスキップ
- 継続行:
  - 行末 `+` / `-` による継続を論理行として結合（可能なら）
  - 第1版では「単一行マッチ優先」。継続結合は第2版でも可
- 空白の正規化: 連続空白を1つに圧縮

### 4.3 検出対象（kind）

| kind | 検出パターン（概念） | label 例 | 階層 |
|------|----------------------|----------|------|
| `pgm` | `PGM` [PARM(...)] | `PGM` / `PGM PARM(...)` | top |
| `endpgm` | `ENDPGM` | `ENDPGM` | top（区切り） |
| `dcl` | `DCL VAR(&x) ...` | `DCL &NAME` | top or under pgm |
| `dclf` | `DCLF FILE(...)` | `DCLF FILE(xxx)` | top or under pgm |
| `label` | `NAME:`（コマンドラベル） | `NAME:` | member |
| `subcommand` | 主要制御コマンド（下記） | コマンド名＋要約 | member |
| `call` | `CALL PGM(...)` | `CALL PGM(xxx)` | member |
| `callprc` | `CALLPRC PRC(...)` | `CALLPRC PRC(xxx)` | member |
| `include` | `INCLUDE` / `COPY` 相当 | `INCLUDE xxx` | top/member |

#### 主要制御コマンド（subcommand）

索引価値の高いものに限定する（全 CL コマンドを列挙しない）:

- 流れ制御: `IF`, `ELSE`, `ENDIF`, `DO`, `DOWHILE`, `DOUNTIL`, `DOFOR`, `ENDDO`, `SELECT`, `WHEN`, `OTHERWISE`, `ENDSELECT`, `GOTO`, `ITERATE`, `LEAVE`, `RETURN`
- 変数: `CHGVAR`, `DCL`, `DCLF`
- 実行: `CALL`, `CALLPRC`, `TFRCTL`, `SBMJOB`, `RETURN`
- メッセージ: `SNDPGMMSG`, `RCVMSG`, `MONMSG`
- ファイル/OBJ: `CRTxxx`, `DLTxxx`, `CHKOBJ`, `RTVxxx` は **デフォルトでは索引化しない**（ノイズ過多）

第1版の推奨セット（必須）:

```
PGM, ENDPGM,
DCL, DCLF,
CALL, CALLPRC, TFRCTL, SBMJOB,
IF, ELSE, ENDIF,
DO, DOWHILE, DOUNTIL, DOFOR, ENDDO,
SELECT, WHEN, OTHERWISE, ENDSELECT,
GOTO, labels (NAME:),
MONMSG, RETURN,
CHGVAR,
INCLUDE
```

### 4.4 階層モデル

```
PGM
├── DCL / DCLF （宣言部）
├── label / 制御コマンド / CALL ...
ENDPGM
```

- `PGM`〜`ENDPGM` を1つのプログラム単位として top に置く
- 宣言と実行要素は `members` に格納
- ソースに複数 `PGM` がある場合（稀）は複数 top エントリ

### 4.5 インデックス出力例

```
Index for: BATCH01.CLLE
---
  1. L1 PGM
      2. L2 DCL &MODE
      3. L3 DCL &RTN
      4. L4 DCLF FILE(CUSTPF)
      5. L10 INIT:
      6. L12 CHGVAR &MODE
      7. L20 CALL PGM(CUSTRPT)
      8. L30 MONMSG MSGID(CPF0000)
      9. L40 IF COND(...)
     10. L55 ENDDO
  11. L60 ENDPGM
---
Total definitions: 11
```

### 4.6 正規表現方針（実装メモ）

- 行頭（leading space 許容）からコマンド名
- 例:
  - `^\s*PGM\b`
  - `^\s*DCL\s+VAR\((&[\w@#$]+)`
  - `^\s*DCLF\b`
  - `^\s*CALL\s+PGM\(([^)]+)\)`
  - `^\s*([A-Z][\w@#$]*)\s*:\s*$`（ラベル）
  - `^\s*MONMSG\b`
- コマンド名は upper 化してから照合
- ラベルとキーワードの衝突はキーワード優先で除外

### 4.7 スコープ外 / 制限

- ~~ネストした `IF/DO` のブロック範囲~~ → v2 で ENDIF/ENDDO/ENDSELECT 対応済み（ネストはスタックで処理）
- プロンプト／画面対話 CL の特別扱い（SNDRCVF 等は索引化のみ）
- マクロ展開
- EBCDIC バイナリソース（テキスト化済み前提）

______________________________________________________________________

## 5. dds2idx 仕様

### 5.1 対象ファイル

| 拡張子 | 種別 |
|--------|------|
| `.pf` | Physical File |
| `.lf` | Logical File |
| `.dspf` | Display File |
| `.prtf` | Printer File |
| `.dds` | 汎用 DDS |

内容から種別を推定できる場合は label に反映する（例: `PF`, `LF`）。

### 5.2 DDS の表記前提

DDS は伝統的に **固定列** だが、IBM i ソースやリポジトリ上では次が混在する:

1. 純固定列（列位置が意味を持つ）
2. スペース整形されたテキストエクスポート
3. 先頭シーケンス番号付き

第1版の方針:

- **固定列を優先**して解釈を試みる
- 列が崩れている場合は **トークン／正規表現フォールバック**
- コメント行:
  - 列7が `*`（固定形式）
  - または行 head が `*` / `A*`

#### 固定列の目安（共通）

一般的な DDS 仕様書イメージ（実装時に実ソースで校正）:

| 列 | 意味 |
|----|------|
| 1–5 | シーケンス（任意） |
| 6 | フォームタイプ（通常 `A`） |
| 7 | コメント `*` / 継続など |
| 8–16 付近 | 名前（レコード／項目） |
| 17 | 参照等 |
| 17–24 付近 | 長さ |
| 24–32 付近 | データ型 |
| 45–80 付近 | キーワード（`TEXT`, `COLHDG`, `JREF`, `EDTCDE`, `DSPATR` 等） |

> 実装時は代表的な PF/LF/DSPF サンプルで列オフセットを検証し、本節を更新すること。

### 5.3 検出対象（kind）

| kind | 意味 | label 例 | 備考 |
|------|------|----------|------|
| `file_keyword` | ファイルレベルキーワード | `UNIQUE`, `REF(x)`, `ALTSEQ` | レコードより前 |
| `record` | レコード形式 `R name` | `R CUSTREC` | 主構造 |
| `field` | 項目定義 | `CUSTID 10A` | record の member |
| `key` | キー項目 `K` | `K CUSTID` | record の member |
| `select_omit` | `S` / `O` 行 | `S STATUS` | LF |
| `join` | JOIN/JREF 関連 | `J` / `JREF(1)` | LF |
| `keyword` | 行キーワード要約 | `TEXT(...)` `COLHDG(...)` | 必要なら field に付帯 |
| `indicator` | DSPF インジケータ | `N01` / `50` 等 | DSPF |
| `layout` | DSPF 位置・定数 | `12  5 'Title'` | DSPF 第2版でも可 |

#### 第1版の必須セット

```
record (R),
field,
key (K),
file_keyword (UNIQUE, REF, ... 主要のみ),
select/omit (S/O) for LF,
join markers for LF,
DSPF: record + field + 主要キーワード（DSPATR, REFRESH, OVERLAY 等は record/field 付帯）
```

### 5.4 階層モデル

```
[file_keyword...]
RECORD (R name)
├── field
├── field
├── key
└── select/omit / join
RECORD (R other)
└── ...
```

- `record` が top（または file_keyword の後の top）
- field/key/select は record の `members`
- ファイルレベルキーワードは record より前の独立 top エントリ

### 5.5 インデックス出力例（PF）

```
Index for: CUSTPF.PF
---
  1. L1 UNIQUE
  2. L2 R CUSTREC
      3. L3 CUSTID 10A
      4. L4 CUSTNAME 30A
      5. L5 BALANCE 9P2
      6. L6 K CUSTID
---
Total definitions: 6
```

### 5.6 インデックス出力例（LF）

```
Index for: CUSTL1.LF
---
  1. L1 R CUSTREC PFILE(CUSTPF)
      2. L2 K CUSTNAME
      3. L3 K CUSTID
      4. L4 S STATUS
---
Total definitions: 4
```

### 5.7 インデックス出力例（DSPF）

```
Index for: CUSTD.DSPF
---
  1. L1 R HEADER
      2. L5 TITLE const
  3. L10 R BODY
      4. L12 CUSTID
      5. L13 CUSTNAME
      6. L20 SFLCTL
---
Total definitions: 6
```

### 5.8 種別ヒント

ファイル内容や拡張子から `file_type` を内部保持し、index ヘッダに出せるとよい（任意）:

```
Index for: CUSTPF.PF (PF)
```

推定ルール:

| 手がかり | 推定 |
|----------|------|
| ext `.pf` / `PFILE` なしの `R` + 項目長 | PF |
| `PFILE(` / `JFILE(` / `S`/`O` キー | LF |
| `DSPATR` / `CF0n` / `SFL` / 行・列位置 | DSPF |
| `SPACEB` / `SKIPB` / `HR` | PRTF |

### 5.9 スコープ外（dds2idx 第1版）と残件

実装済み（取り消し線）と、**意図的に残すスコープ外**を分離する。

#### 実装済み（旧スコープ外 → 取り込み済み）

- ~~表示属性ビットの完全デコード~~ → v2.2 で DSPATR/COLOR/CF/条件インジケータ・定数行をデコード
- ~~`REF` 先の他ファイル解決（名前の記録のみ）~~ → v2.1 で同一 workdir 簡易追従を実装

#### 残件（スコープ外・実装しない / 後回しのまま）

| 項目 | 理由 / 方針 |
|------|-------------|
| マルチライブラリ / 完全な IBM i オブジェクト解決 | workdir 浅探索・深さ 1 のみ。`*LIBL` や実オブジェクトカタログは対象外 |
| DSPATR 全ビット組合せの意味論的展開 | 索引は引数文字列（`HI UL` 等）を保持。表示エンジン相当の組合せ解釈はしない |
| PRTF 印刷座標のレンダリング | 座標の索引記録は可。ページ/オーバーレイ描画はしない |
| ICF / 特殊デバイスファイル | 対象外 |
| バイナリ保存ソース | 対象外 |
| EBCDIC ソース読込 | `read_index_source` は utf-8-sig/utf-8/cp932/shift_jis/euc_jp のみ |
| `ibmi2idx` 自動ディスパッチャ | **作らない**（拡張子→ツールは LLM + description） |

______________________________________________________________________

## 6. TOOL_SPEC 草案

### 6.1 cl2idx

```python
TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "cl2idx",
        "description": (
            "Parse an IBM i CL/CLP/CLLE (.cl/.clp/.clle) file into program entry, "
            "declarations, labels, control commands, and calls, and return a numbered "
            "index or a specific definition section. Use this when you need to read a "
            "large CL source: first call with mode='index', then mode='section'."
        ),
        "x_search_terms": [
            "read cl file",
            "clle index",
            "clp program structure",
            "IBM i CL",
            "CLソースを読む",
            "CLプログラム構造",
        ],
        "x_search_terms_en": [
            "read cl file",
            "clle index",
            "clp program structure",
            "IBM i CL",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the CL/CLP/CLLE source file.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": (
                        "\"index\" returns a numbered table of contents with line numbers. "
                        "\"section\" returns a specific definition by number."
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": (
                        "Section number to retrieve (used only when mode='section'). "
                        "Get the number from the index output."
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}
```

### 6.2 dds2idx

```python
TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "dds2idx",
        "description": (
            "Parse an IBM i DDS source (PF/LF/DSPF/PRTF; .pf/.lf/.dspf/.prtf/.dds) into "
            "records, fields, keys, and file-level keywords, and return a numbered index "
            "or a specific definition section. Use this when you need to read a large DDS "
            "file: first call with mode='index', then mode='section'."
        ),
        "x_search_terms": [
            "read dds file",
            "physical file dds",
            "display file dspf",
            "logical file lf",
            "DDSを読む",
            "PF LF DSPF 定義",
        ],
        "x_search_terms_en": [
            "read dds file",
            "physical file dds",
            "display file dspf",
            "logical file lf",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the DDS (PF/LF/DSPF/PRTF) source file.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": (
                        "\"index\" returns a numbered table of contents with line numbers. "
                        "\"section\" returns a specific definition by number."
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": (
                        "Section number to retrieve (used only when mode='section'). "
                        "Get the number from the index output."
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}
```

______________________________________________________________________

## 7. 実装タスク

### 7.1 実装順序

1. **helpers 確認**  
   `index_tool_helpers.read_index_source` / `resolve_index_path` を再利用
2. **cl2idx 実装**  
   パターンが単純なため先に実装・テスト
3. **dds2idx 実装**  
   固定列＋フォールバック
4. **i18n JSON**
5. **DEVELOP.md / DEVELOP.ja.md の表更新**
6. **サンプルソースでの手動検証**
7. **（任意）pytest**  
   `tests/` に最小 fixture

### 7.2 実装クラス案

```
# cl2idx_tool.py
class _ClIndexBuilder:
    def __init__(self, source: str, filepath: str = "")
    def _prepare_line(self, line: str) -> str
    def _normalize(self, line: str) -> str
    def _detect(self, line: str) -> list[tuple[str, str]]
    def _parse(self) -> None
    def _assign_end_lines(self, entries: list[dict]) -> None
    def build_index(self) -> str
    def get_section(self, n: int) -> str | None
    def section_count(self) -> int

# dds2idx_tool.py
class _DdsIndexBuilder:
    ...  # 同様。_prepare_line で固定列コメント/シーケンス処理
```

`run_tool` は `cobol2idx_tool.run_tool` と同型。

### 7.3 テスト観点

#### cl2idx

- 最小 PGM（DCL + CALL + ENDPGM）
- ラベルと GOTO
- IF/DO ネスト（開始行が索引に出ること）
- MONMSG
- 空ファイル / コメントのみ
- section 範囲取得が次要素直前で切れること

#### dds2idx

- 単純 PF（R + fields + K）
- LF（PFILE, 複合キー, S/O）
- DSPF（複数 record）
- コメント行スキップ
- シーケンス番号付き行
- section で record 単位が field 群を含むこと

### 7.4 完了条件

- [x] `cl2idx_tool.py` / `.json` 追加
- [x] `dds2idx_tool.py` / `.json` 追加
- [x] `python -m py_compile` 通過
- [x] `ruff check` / `ruff format` 通過
- [x] DEVELOP.md / DEVELOP.ja.md 更新
- [x] 代表サンプルで index → section が実用的
- [x] pytest: `tests/test_cl2idx_tool.py`, `tests/test_dds2idx_tool.py`

______________________________________________________________________

## 8. ドキュメント反映案

`DEVELOP.md` の `*2idx` 表に行追加:

| Tool | File(s) | Parser | Detects |
|------|---------|--------|---------|
| `cl2idx` | .cl/.clp/.clle | regex | pgm, dcl, dclf, label, call, control commands, monmsg |
| `dds2idx` | .pf/.lf/.dspf/.prtf/.dds | regex (fixed-column aware) | record, field, key, select/omit, file keywords, REF/REFFLD follow, DSPF indicator/attr/const |

`DEVELOP.ja.md` も同様。

______________________________________________________________________

## 9. リスクと緩和

| リスク | 緩和 |
|--------|------|
| CL 継続行でコマンド分割 | 第1版は単一行。既知制限として明記 |
| DDS 列位置の方言差 | 固定列失敗時にトークンフォールバック |
| コマンド全列挙によるノイズ | 制御・呼出・宣言に限定 |
| LLM が cobol2idx を誤用 | description / x_search_terms で CL・DDS を明示 |
| 巨大 DSPF の定数行だらけ | layout 行は第2版。第1版は record/field 中心 |

______________________________________________________________________

## 10. 拡張状況（v2 以降）

### 取り込み済み（v2 / v2.1）

- CL 継続行（`+` / `-`）の結合
- IF/DO/SELECT と ENDIF/ENDDO/ENDSELECT の end_line 対応
- 複数行 `/* */` コメント除去、SEU シーケンス番号除去
- DCL TYPE/LEN・CALL/MONMSG ラベル強化
- DDS SEU 固定列の複数レイアウト試行
- DSPF 定数行・SFLCTL・フィールドキーワード付帯（TEXT/COLHDG）
- ファイル種別推定のスコアリング
- DDS `REF` / `REFFLD` 先の簡易追従（同一 workdir 内、深さ 1）
  - `REF(file)` / `REF(lib/file)` をソース隣・workdir 浅探索で解決
  - 参照フィールド（`R` / `REFFLD`）に型情報を注釈（例: `CUSTID R 10A <= CUSTPF.CUSTID`）
  - 未解決時は `REF(...) [not found]` / `[ref? NAME]`
  - 循環参照は `_ref_stack` + depth limit で抑止
- DSPF 表示属性・インジケータ詳細デコード
  - 条件インジケータ（`01` / `N02` / `41N42`）をラベル・meta に付与
  - `DSPATR(...)` / `COLOR(...)` / `CFnn(...)` 引数を保持（field 付帯・単独 keyword）
  - packed 定数行（`5  2'Name'`）を layout として検出（form-type `A` の誤 field 化を抑止）

### 取り込み済み（打ち消し・完了）

- ~~DSPF インジケータ詳細・表示属性ビットの完全デコード~~ → 実装済み（条件インジケータ・DSPATR/COLOR/CF 引数・packed 定数行）
- ~~`rpg2idx`（RPG/RPGLE）の新規仕様~~ → 実装済み（`rpg2idx_tool`。埋め込み SQL・`/IF`・主要固定桁パス含む）

### 残件（IBM i *2idx 共通・意図的スコープ外）

実装対象の残作業は **なし**。以下はドキュメント上の残件（やらないこと）として固定する。

| 領域 | 残件 | 備考 |
|------|------|------|
| 共通 | EBCDIC ソース | `read_index_source`: utf-8-sig/utf-8/cp932/shift_jis/euc_jp のみ |
| 共通 | `ibmi2idx` ディスパッチャ | **作らない**（LLM + description でツール選択） |
| `dds2idx` | マルチライブラリ / 完全オブジェクト解決 | 同一 workdir・深さ 1 の REF のみ |
| `dds2idx` | DSPATR 全ビット組合せの意味論 | 引数文字列保持まで |
| `dds2idx` | PRTF 座標レンダリング | 索引のみ |
| `dds2idx` | ICF / 特殊デバイス / バイナリソース | 対象外 |
| `rpg2idx` | 固定桁の全方言バリアント | 主要 F/D/P/C/H/I/O パスのみ |
| `rpg2idx` | 埋め込み SQL の詳細意味解析 | `EXEC SQL` の索引化まで（文意味の完全展開はしない） |
| `rpg2idx` | `/IF` の評価実行 | 条件コンパイル行の検出・索引まで（式の評価はしない） |

詳細は §5.9 および各ツールの pytest（`tests/test_cl2idx_tool.py` / `test_dds2idx_tool.py` / `test_rpg2idx_tool.py`）を正とする。

______________________________________________________________________

## 11. 決定事項サマリ

| 項目 | 決定 |
|------|------|
| cobol2idx への統合 | **しない** |
| 新ツール | `cl2idx`, `dds2idx`（`rpg2idx` は別ツールとして実装済み） |
| インタフェース | 既存 `*2idx` と同一 |
| パーサ | 正規表現（DDS は固定列意識） |
| 依存 | stdlib のみ |
| 第1版範囲 | 構造索引に十分な主要要素のみ |
| 実装状態 | v2 + REF follow + DSPF indicator/attr/const + rpg2idx 済み |
| 実装残作業 | **なし**（下表はスコープ外の固定残件のみ） |
| スコープ外残件 | EBCDIC / マルチ lib オブジェクト解決 / DSPATR 意味論フル展開 / PRTF 描画 / ICF・binary / RPG 全固定桁方言・SQL//IF 意味評価 / `ibmi2idx` 非作成 |
