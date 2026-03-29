# Pythonテクニック（定石）集

各項目は「何が嬉しいか / 使いどころ / 例 / 注意」で最小限に整理。

______________________________________________________________________

## 1) f-string（文字列埋め込み）

- 何が嬉しいか: 読みやすい・速い・フォーマットがまとまる。
- 使いどころ: ログ/例外メッセージ/表示用文字列。
- 例:

```py
name = "Alice"
age = 30
msg = f"{name} ({age=})"
```

- 注意:
  - ユーザー入力をそのまま出す場合は、機密情報やログ注入に配慮。
  - 日時/数値の書式は `f"{dt:%Y-%m-%d}"` / `f"{x:.3f}"` のように指定。

______________________________________________________________________

## 2) pathlib（パス操作）

- 何が嬉しいか: OS差異に強い / 文字列結合より安全。
- 使いどころ: ファイル列挙、拡張子判定、出力先の組み立て。
- 例:

```py
from pathlib import Path

out_dir = Path("outputs")
out_dir.mkdir(parents=True, exist_ok=True)
path = out_dir / "result.json"
```

______________________________________________________________________

## 3) enumerate / zip（添字・並行走査）

- 何が嬉しいか: インデックス管理のバグを減らす。

```py
for i, item in enumerate(items, start=1):
    ...

for a, b in zip(xs, ys, strict=True):
    ...
```

- 注意:
  - `zip(..., strict=True)`（Python 3.10+）で長さ不一致を検知できる。

______________________________________________________________________

## 4) 内包表記（comprehension）

- 何が嬉しいか: 「変換/フィルタ」が短く書ける。

```py
names = [u.name for u in users if u.active]
by_id = {u.id: u for u in users}
```

- 注意:
  - 複雑になったら普通の `for` に戻す（可読性優先）。

______________________________________________________________________

## 5) dict の安全な取得（get / setdefault / defaultdict / Counter）

- 何が嬉しいか: KeyError回避、集計が短くなる。

```py
count = d.get(key, 0)

from collections import defaultdict, Counter
acc = defaultdict(int)
acc[key] += 1

c = Counter(words)
```

______________________________________________________________________

## 6) unpacking（アンパック）

```py
a, b = pair
head, *tail = seq
merged = {**a, **b}
```

- 注意:
  - 代入は「要素数が合う」前提。合わない可能性があるなら防御的に。

______________________________________________________________________

## 7) dataclass（小さなデータ構造）

- 何が嬉しいか: ボイラープレート削減、意図が明確。

```py
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    id: int
    name: str
```

- 注意:
  - 不変にしたいなら `frozen=True` を検討。

______________________________________________________________________

## 8) typing（型ヒント）

- 何が嬉しいか: 読み手の理解が速い、IDE支援、リファクタ安全性。

```py
def parse_ids(text: str) -> list[int]:
    ...
```

- 注意:
  - 「公開API」「境界（入出力）」から付けると効きやすい。

______________________________________________________________________

## 9) 例外設計（raise from / 例外の粒度）

- 何が嬉しいか: 原因追跡がしやすい、失敗時の挙動が安定。

```py
try:
    ...
except ValueError as e:
    raise RuntimeError("invalid input") from e
```

- 指針:
  - その場で回復できない例外は「文脈を足して再送出」。
  - 何でも `except Exception:` は最後の砦（ログして再送出/適切な終了）。

______________________________________________________________________

## 10) context manager（with）

- 何が嬉しいか: 後始末漏れを防ぐ。

```py
from pathlib import Path

data = Path("in.txt").read_text(encoding="utf-8")
```

- 注意:
  - I/O は `Path.read_text/read_bytes` も検討（短い処理なら読みやすい）。

______________________________________________________________________

## 11) logging（print から移行）

- 何が嬉しいか: レベル/出力先/フォーマットを後から制御できる。

```py
import logging
logger = logging.getLogger(__name__)

logger.info("start")
logger.exception("failed")
```

- 注意:
  - ライブラリ側は基本 `basicConfig` を呼ばない（アプリ側で設定）。

______________________________________________________________________

## 12) match-case（構造的パターンマッチ）

- 何が嬉しいか: 分岐が読みやすい（条件の集合が明確）。

```py
match kind:
    case "csv":
        ...
    case "json":
        ...
    case _:
        raise ValueError(kind)
```

______________________________________________________________________

## 13) walrus（:=）

- 何が嬉しいか: 「計算→判定」を1回にまとめられる。

```py
if (m := pattern.search(text)):
    return m.group(1)
```

- 注意:
  - 多用すると読みにくい。繰り返し値を使う時だけ。
