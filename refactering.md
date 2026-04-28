# Refactoring plan

## 目的
- `src/uagent` 配下の大きいモジュールを分割する
- 保守性を上げつつ、性能を落とさない
- 既存参照を壊しにくい移行にする

## 優先方針
- hot path は浅く保つ
- 細分化しすぎない
- 重い依存は遅延 import にする
- 旧パスは当面互換ラッパーとして残す

## まず候補にするモジュール
1. `src/uagent/runtime_init.py`
2. `src/uagent/cli.py` / `src/uagent/gui.py` / `src/uagent/web.py` / `src/uagent/scheckgui.py`
3. `src/uagent/uagent_llm.py`
4. `src/uagent/util_tools.py`
5. `src/uagent/core.py`

## 推奨ディレクトリ案
```text
src/uagent/
  runtime/
    __init__.py
    init.py
    workdir.py
    banner.py
    env.py
    memory.py

  ui/
    __init__.py
    cli.py
    gui.py
    web.py
    scheckgui.py

  llm/
    __init__.py
    orchestrator.py
    responses.py
    errors.py
    tool_narrowing.py

  tooling/
    __init__.py
    callbacks.py
    specs.py
    trace.py
    catalog.py
```

## 移行ルール
- 新ファイルを先に追加する
- 旧ファイルは削除せず、再exportする薄い互換層にする
- 外部参照を段階的に新パスへ移す
- 最後に互換層を整理する

## 互換性の例
```python
# src/uagent/uagent_llm.py
from .llm.orchestrator import *
```

## 壊れやすい点
- `__init__.py` での再export過多
- 循環 import
- 起動時に重いモジュールを一括 import

## 進め方
1. `runtime/` を切る
2. `ui/` を切る
3. `uagent_llm.py` を分割する
4. `util_tools.py` を分割する
5. `core.py` を整理する

## 補足
- まずは分離を優先
- 共通化は後で行う
- 性能確認は変更ごとに行う
