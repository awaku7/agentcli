# Araç Oluşturma Kılavuzu

Bu kılavuz, **uag'ın kendisini değiştirmeden** kendi araçlarınızı uag'a nasıl ekleyeceğinizi açıklar.
Uag kaynak ağacına doğrudan bir araç eklemek istiyorsanız, bkz.
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## İçindekiler

1. [Temel Araç Yapısı](#1-temel-araç-yapısı)
2. [Python Aracı Oluşturma](#2-bir-python-aracı-oluşturma)
3. [Bir Rust + Python Aracı Oluşturma](#3-pas-yaratma--python-aracı)
4. [TOOL_SPEC Referansı](#4-tool_spec-reference)
5. [Uluslararasılaştırma (i18n)](#5-uluslararasılaştırma-i18n)
6. [Test Etme ve Hata Ayıklama](#6-test-etme-ve-hata-ayıklama)
7. [Referans Örnekleri](#7-reference-examples)

---

## 1. Temel Araç Yapısı

Bir araç aşağıdaki öğelerden oluşur:

| Eleman | Gerekli | Açıklama |
|-----------|----------|------------|
| 'TOOL_SPEC' | Evet | Aracın adını, açıklamasını ve parametrelerini tanımlayan sözlük |
| `run_tool(args)` | Evet | Araç çağrıldığında yürütülen işlev. Args bir diktedir, dönüş ise bir dizedir. |
| i18n JSON | Önerilen | Çeviri JSON dosyası (aynı temel ad, `<name>_tool.json`) |

### Minimal Python Aracı

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

## 2. Python Aracı Oluşturma

### Adımlar

1. **`UAGENT_EXTERNAL_TOOLS_DIRS` ortam değişkenini ayarlayın** (zaten ayarlanmamışsa)

 Örnek:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Birden fazla dizin `:` (Linux/macOS) veya `;` (Windows) ile ayrılabilir.
 `UAGENT_EXTERNAL_TOOLS_DIR` (tekil) aynı zamanda geriye dönük uyumluluk açısından da desteklenir.

2. **Python dosyası oluşturun**

 Dosya adı ücretsizdir, ancak `<name>_tool.py` adlandırması önerilir (ör. `my_tool.py`).

3. **Gerekli öğeleri uygulayın**

 - `TOOL_SPEC` sözlüğü
 - `run_tool(args)` işlevi
 - İsteğe bağlı olarak bir i18n JSON dosyası

4. **Aracıyı yeniden başlatın** (veya `system_reload` aracını çalıştırın)

### Tam Şablon

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

i18n ayrıntıları için [Bölüm 5](#5-internationalization-i18n)'ye bakın.

---

## 3. Rust + Python Aracı Oluşturma

Rust uygulaması, performans açısından kritik görevler (yoğun veri işleme, kriptografi, dosya işleme vb.) için idealdir.
uag, önceden oluşturulmuş `.pyd` dosyalarını doğrudan yükleyebilir, bu nedenle **son kullanıcılar `pip kurulumuna` gerek duymaz**.

### Araç Yapısı

Bir Rust aracı aşağıdakilerden oluşur: dosyalar:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Dağıtım için, `_tool.py` + `_tool.json` + `.pyd` dosyalarını 
`UAGENT_EXTERNAL_TOOLS_DIRS` içine yerleştirin.

### Adımlar

#### Adım 1: Rust projesini oluşturun

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

#### 2. Adım: Rust uygulaması (src/lib.rs)

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

**Anahtar noktalar:**
- İşlevleri `#[pyfunction(name = "run_<name>")] ile gösterme
- Dönüş türü `PyResult<String>`
- `#[pymodule]` işlev adı eşleşmelidir sandık adı (`my_rust_tools`)

#### 3. Adım: Oluşturun

```bash
cd my_rust_tool
cargo build --release
```

Windows: `target/release/my_rust_tools.dll` dosyasını `my_rust_tools.pyd` olarak yeniden adlandırın
Linux: yeniden adlandır `target/release/libmy_rust_tools.so`'yu `my_rust_tools.so`
macOS: `target/release/libmy_rust_tools.dylib`i `my_rust_tools.so` olarak yeniden adlandırın

Veya kullanarak maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### 4. Adım: Python sarmalayıcısını oluşturun

`UAGENT_EXTERNAL_TOOLS_DIRS` dosyanızda `my_rust_tool.py`yi oluşturun dizin:

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

**``load_rust_pyd()`` çözünürlük sırası:**

1. `.py`
2 sarmalayıcısıyla aynı dizinde `<module_name>.pyd` (veya `.so`) ifadesini arayın. Pip yüklü bir modüle geri dönün

#### 5. Adım: Dağıtım

Yalnızca bu 3 dosyaya ihtiyaç vardır. Son kullanıcıların **pip kurulumuna" ihtiyacı yoktur.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Notlar

- **Yalnızca derleme zamanı:** Pas takım zinciri ve "maturin" gereklidir
 ```bash
  pip install maturin
  ```
- Rust sandık adı ("Cargo.toml" içindeki "[lib] name`), `load_rust_pyd()`'in ilk argümanıyla eşleşmelidir
- Sarmalayıcı dosya adı ve `.pyd` konumu, aynı dizinde oldukları sürece bağımsızdır

---

## 4. TOOL_SPEC Referansı

### Temel Yapı

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

### Özellikler

| Alan | Tür | Açıklama |
|----------|------|-------------|
| 'tür' | dizi | Her zaman `"işlev"` |
| 'x_build' | dizi | Rust uygulaması için `"rust"` (Python için atlayın) |
| `araç_türü' | dizi | Tür adı (isteğe bağlı). Türe dayalı kontrolü etkinleştirir |
| 'araç_seviyesi' | int | 0=etkin, 1=koşullu (varsayılan), -1=devre dışı |
| 'işlev.adı' | dizi | **Gerekli**. Araç adı (küçük harf + rakamlar + alt çizgi) |
| 'işlev.açıklama' | dizi | **Gerekli**. Açıklama |
| `function.x_search_terms` | liste[str] | i18n uyumlu arama anahtar kelimeleri (`_(...)` ile sarın) |
| `function.x_search_terms_en` | liste[str] | Sabit İngilizce arama anahtar kelimeleri |
| 'işlev.parametreler' | dikte | Parametre tanımı (OpenAI işlev çağırma formatı) |

---

## 5. Uluslararasılaştırma (i18n)

### Çeviri Mekanizması

`make_tool_translator(__file__)` çağrıldığında, çeviriler aynı taban adı ile bir `.json` dosyasından
dizin.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Çeviri Anahtarlarını Kullanma

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### JSON Dosya Formatı

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

Mevcut olanı görüntüle Desteklenen dil kodları için `_tool.json` dosyaları.

---

## 6. Test Etme ve Hata Ayıklama

### Sözdizimi Kontrolü

```bash
python -m py_compile my_tool.py
```

### Doğrulama Aracı Yükleniyor

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Hata Günlükleri

Takım yükleme sırasındaki hatalar stderr'e yazdırılır. Aracınız yüklü değilse,
uag başlangıç ​​günlüklerini kontrol edin.

---

## 7. Referans Örnekleri

### Python Aracı Örnekleri

- `date_calc_tool.py` (`src/uagent/tools/` içinde) — Tarih hesaplama. Harici olarak kopyalayın ve özelleştirin.
- `calculator_tool.py` (`src/uagent/tools/` içinde) — Hesap Makinesi.

### Rust Aracı Örnekleri

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` içinde) — UUID oluşturma
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (`src/uagent/tools_rust/` içinde) — Slug dönüşümü

Harici olarak kullanmak için `_tool.py` ve `.pyd` dosyalarını `UAGENT_EXTERNAL_TOOLS_DIRS` içine kopyalayın araçlar.

### Harici Araç Dizinlerini Ayarlama

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Birden çok dizin `:` (Linux/macOS) veya `;` (Windows) ile ayrılabilir.
`UAGENT_EXTERNAL_TOOLS_DIR` (tekil) de geriye dönük uyumluluk için desteklenir.