# 도구 생성자 가이드

이 가이드는 **uag 자체를 수정하지 않고** uag에 자신만의 도구를 추가하는 방법을 설명합니다.
uag 소스 트리에 직접 도구를 추가하려면, 
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md)를 참조하세요.

---

## 목차
0. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [기본 도구 구조](#1-기본-도구-구조)
2. [Python 도구 만들기](#2-creating-a-python-tool)
3. [Rust + Python 도구 만들기](#3-creating-a-rust--python-tool)
4. [TOOL_SPEC 참조](#4-tool_spec-reference)
5. [국제화(i18n)](#5-국제화-i18n)
6. [테스트 및 디버깅](#6-테스트-및-디버깅)
7. [참조 예](#7-reference-examples)

---

## 0. Quick Start: Scaffold Command

The easiest way to create a new tool is to use the **`:tool create`** command
from the CLI prompt. It generates the boilerplate files automatically.

### Usage

```
:tool create <name> --lang python|rust [--description '...'] [--output-dir <dir>]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `<name>` | Yes | Tool name (e.g., `my_search`, `file_processor`) |
| `--lang` | No | `python` (default) or `rust` |
| `--description` | No | Short description of the tool |
| `--output-dir` | No | Output directory (default: first path in `UAGENT_EXTERNAL_TOOLS_DIRS`, or current directory) |

### Examples

```text
# Python tool
:tool create my_search --lang python --description "Custom search tool"

# Rust tool
:tool create heavy_processor --lang rust --description "Heavy data processor"
```

### What Gets Generated

**Python (`--lang python`)**:
- `<name>_tool.py` — Tool implementation with `TOOL_SPEC` and `run_tool()`
- `<name>_tool.json` — i18n translation template

Both files are ready to use. Place them in your `UAGENT_EXTERNAL_TOOLS_DIRS`
and restart the agent (or run `system_reload`).

**Rust (`--lang rust`)**:
- `<name>/` — Cargo project directory with `Cargo.toml`, `pyproject.toml`, and `src/lib.rs`
- `<name>_tool.py` — Python wrapper that loads the compiled `.pyd`

After scaffolding, build and install:

```bash
cd <name>
maturin build --release
pip install target/wheels/*.whl
```

Then place `<name>_tool.py` and the built `.pyd` in your
`UAGENT_EXTERNAL_TOOLS_DIRS` and restart the agent.

---


## 1. 기본 도구 구조

도구는 다음 요소로 구성됩니다.

| 요소 | 필수 | 설명 |
|---------|----------|------------|
| '도구_사양' | 예 | 도구의 이름, 설명, 매개변수를 정의하는 사전 |
| `run_tool(args)` | 예 | 도구가 호출될 때 실행되는 함수입니다. Args는 dict이고 return은 문자열입니다. |
| i18n JSON | 추천 | JSON 파일 번역(동일한 기본 이름, `<name>_tool.json`) |

### 최소 Python 도구

```python
# my_tool.py
from typing import Any

def run_tool(args: dict[str, Any]) -> str:
    name = args.get("name", "World")
    return f"Hello, {name}!"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Says hello.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to greet",
                },
            },
        },
    },
}
```

---

## 2. Python 도구 만들기

### 단계

1. **`UAGENT_EXTERNAL_TOOLS_DIRS` 환경 변수를 설정합니다**(아직 설정되지 않은 경우)

 예:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 여러 디렉터리는 `:`(Linux/macOS) 또는 `;`(Windows)으로 구분할 수 있습니다.
 `UAGENT_EXTERNAL_TOOLS_DIR` (단수)도 이전 버전과의 호환성을 위해 지원됩니다.

2. **Python 파일 만들기**

 파일 이름은 자유지만 `<name>_tool.py` 이름을 사용하는 것이 좋습니다(예: `my_tool.py`).

3. **필수 요소 구현**

 - `TOOL_SPEC` 사전
 - `run_tool(args)` 함수
 - 선택적으로 i18n JSON 파일

4. **에이전트 다시 시작**(또는 `system_reload` 도구 실행)

### 전체 템플릿

```python
from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def run_tool(args: dict[str, Any]) -> str:
    """Execute the tool."""
    input_text = args.get("input", "")
    result = f"Processed: {input_text}"
    return result


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": _(
            "tool.description",
            default="Description of my_tool",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["my_tool", "keyword1"],
        ),
        "x_search_terms_en": ["my_tool", "keyword1"],
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": _("param.input", default="Input text"),
                },
            },
        },
    },
}
```

i18n 세부정보는 [섹션 5](#5-internationalization-i18n)를 참조하세요.

---

## 3. Rust + Python 도구 만들기

Rust 구현은 성능이 중요한 작업(많은 데이터 처리, 암호화, 파일 처리 등)에 이상적입니다.
uag는 미리 빌드된 `.pyd` 파일을 직접 로드할 수 있으므로 **최종 사용자는 `pip install`이 필요하지 않습니다**.

### 도구 구조

Rust 도구는 다음으로 구성됩니다. 파일:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

배포를 위해 `_tool.py` + `_tool.json` + `.pyd` 파일을
`UAGENT_EXTERNAL_TOOLS_DIRS`에 배치합니다.

### 단계

#### 1단계: 생성 Rust 프로젝트

**Cargo.toml**
```toml
[package]
name = "my_rust_tools"
version = "0.1.0"
edition = "2021"

[lib]
name = "my_rust_tools"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.29", features = ["extension-module", "abi3-py311"] }
```

**pyproject.toml**
```toml
[build-system]
requires = ["maturin>=1.0"]
build-backend = "maturin"]

[project]
name = "my_rust_tools"
version = "0.1.0"
requires-python = ">=3.11"
```

#### 2단계: Rust 구현 (src/lib.rs)

```rust
use pyo3::prelude::*;
use std::collections::HashMap;

#[pyfunction(name = "run_my_operation")]
pub fn run(args: HashMap<String, Py<PyAny>>) -> PyResult<String> {
    let py = unsafe { Python::assume_attached() };

    let input: String = args
        .get("input")
        .and_then(|v: &Py<PyAny>| v.bind(py).extract::<String>().ok())
        .unwrap_or_default();

    let result = format!("Rust says: {}", input);
    Ok(result)
}

#[pymodule]
fn my_rust_tools(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run, m)?)?;
    Ok(())
}
```

**핵심 사항:**
- `#[pyfunction(name = "run_<name>")]`을 사용하여 함수 노출
- 반환 유형은 `PyResult<String>`입니다.
- `#[pymodule]` 함수 이름은 크레이트 이름과 일치해야 합니다 (`my_rust_tools`)

#### 3단계: 빌드

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll`의 이름을 `my_rust_tools.pyd`로 변경
Linux: 이름 변경 `target/release/libmy_rust_tools.so`를 `my_rust_tools.so`로 변경
macOS: `target/release/libmy_rust_tools.dylib`를 `my_rust_tools.so`로 이름 바꾸기

또는 maturin 사용:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### 단계 4: Python 래퍼 만들기

`UAGENT_EXTERNAL_TOOLS_DIRS` 디렉터리에 `my_rust_tool.py` 만들기:

```python
from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator
from uagent.tools.rust_helper import load_rust_pyd

_ = make_tool_translator(__file__)

# Place .pyd in the same directory — auto-detected
_rust_mod = load_rust_pyd("my_rust_tools")
run_tool = _rust_mod.run_my_operation

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_build": "rust",
    "function": {
        "name": "my_operation",
        "description": _("tool.description", default="My Rust operation"),
        "x_search_terms": _("x_search_terms", default=["my_operation"]),
        "x_search_terms_en": ["my_operation"],
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": _("param.input", default="Input text"),
                },
            },
        },
    },
}
```

**``load_rust_pyd()`` 해결 순서:**

1. 래퍼 `.py`와 동일한 디렉터리에서 `<module_name>.pyd`(또는 `.so`)를 찾으세요.
2. pip 설치 모듈로 대체

#### 5단계: 배포

이 3개 파일만 필요합니다. 최종 사용자에게는 `pip install`이 **필요하지 않습니다**.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### 참고

- **빌드 시간에만 해당:** Rust 툴체인 및 `maturin`이 필요합니다.
 ```bash
  pip install maturin
  ```
- Rust 상자 이름 (`Cargo.toml`의 `[lib] 이름`)은 `load_rust_pyd()`의 첫 번째 인수와 일치해야 합니다.
- 래퍼 파일 이름과 `.pyd` 위치는 동일한 디렉터리에 있는 한 독립적입니다.

---

## 4. TOOL_SPEC 참조

### 기본 구조

```python
TOOL_SPEC: dict[str, Any] = {
    "type": "function",                     # Fixed
    "x_build": "rust",                      # Only for Rust implementation
    "tool_genre": "utility",                # Genre (optional)
    "tool_level": 0,                        # 0=enabled, 1=conditional, -1=disabled
    "function": {
        "name": "tool_name",                # Tool name (snake_case)
        "description": "...",               # Description
        "x_search_terms": [...],            # Search keywords (i18n-aware)
        "x_search_terms_en": [...],         # English search keywords (fixed)
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "...",
                },
                "param2": {
                    "type": "integer",
                    "description": "...",
                    "enum": [1, 2, 3],
                },
            },
            "required": ["param1"],
        },
    },
}
```

### 속성

| 필드 | 유형 | 설명 |
|-------|------|-------------|
| '유형' | str | 항상 `"기능"` |
| `x_build` | str | Rust 구현의 경우 `"rust"`(Python의 경우 생략) |
| `도구_장르` | str | 장르명(선택). 장르 기반 제어를 활성화합니다 |
| `도구_수준` | 정수 | 0=활성화, 1=조건부(기본값), -1=비활성화 |
| `함수.이름` | str | **필수의**. 도구 이름(소문자 + 숫자 + 밑줄) |
| `함수.설명` | str | **필수의**. 설명 |
| `function.x_search_terms` | 목록[str] | i18n 인식 검색 키워드(`_(...)`로 래핑) |
| `function.x_search_terms_en` | 목록[str] | 영어 검색 키워드 수정 |
| `함수.매개변수` | 사전 | 매개변수 정의(OpenAI 함수 호출 형식) |

---

## 5. 국제화(i18n)

### 번역 메커니즘

`make_tool_translator(__file__)`를 호출하면 동일한 기본 이름을 가진 `.json` 파일에서 번역을 로드합니다
 디렉토리.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### 번역 키 사용

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON 파일 형식

```json
{
    "en": {
        "tool.description": "Default English text",
        "param.input": "Input text"
    },
    "ja": {
        "tool.description": "日本語の説明文",
        "param.input": "入力テキスト"
    }
}
```

참조 지원되는 언어 코드에 대한 기존 `_tool.json` 파일.

---

## 6. 테스트 및 디버깅

### 구문 검사

```bash
python -m py_compile my_tool.py
```

### 도구 확인 로드 중

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### 오류 로그

도구 로드 중 오류가 stderr에 인쇄됩니다. 도구가 로드되지 않은 경우
uag 시작 로그를 확인하세요.

---

## 7. 참조 예제

### Python 도구 예제

- `date_calc_tool.py`(`src/uagent/tools/`에서) — 날짜 계산. 외부에서 복사하고 사용자 정의합니다.
- `calculator_tool.py`(`src/uagent/tools/`에서) — 계산기.

### Rust 도구 예

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd`(`src/uagent/tools_rust/`에서) — UUID 생성
- `rust_slugify_tool.py` + `uag_tools_rust.pyd`(`src/uagent/tools_rust/`에 있음) — 슬러그 변환

`_tool.py` 및 `.pyd` 파일을 `UAGENT_EXTERNAL_TOOLS_DIRS`에 복사하여 외부 도구로 사용합니다.

### 외부 도구 디렉터리 설정

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

여러 디렉터리는 `:`(Linux/macOS) 또는 `;`(Windows)으로 구분할 수 있습니다.
`UAGENT_EXTERNAL_TOOLS_DIR`(단수)도 이전 버전과의 호환성을 위해 지원됩니다.