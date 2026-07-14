# Panduan Pembuat Alat

Panduan ini menjelaskan cara menambahkan alat Anda sendiri ke uag **tanpa memodifikasi uag itu sendiri**.
Jika Anda ingin menambahkan alat langsung ke pohon sumber uag, lihat
[DEVELOP_TOOL.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_TOOL.md).

---

## Daftar Isi

1. [Struktur Alat Dasar](#1-struktur-alat-dasar)
2. [Membuat Alat Python](#2-membuat-alat-python)
3. [Membuat Alat Rust + Python](#3-membuat-a-rust--python-tool)
4. [Referensi TOOL_SPEC](#4-referensi-tool_spec)
5. [Internasionalisasi (i18n)](#5-internasionalisasi-i18n)
6. [Pengujian dan Debug](#6-pengujian-dan-debugging)
7. [Contoh Referensi](#7-contoh-referensi)

---

## 1. Struktur Alat Dasar

Sebuah alat terdiri dari elemen berikut:

| Elemen | Diperlukan | Deskripsi |
|---------|----------|-------------|
| `TOOL_SPEC` | Ya | Kamus yang mendefinisikan nama alat, deskripsi, dan parameter |
| `run_tool(args)` | Ya | Fungsi dijalankan saat alat dipanggil. Args adalah dict, return adalah string. |
| i18n JSON | Direkomendasikan | Terjemahan file JSON (nama dasar yang sama, `<nama>_tool.json`) |

### Minimal Python Tool

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

## 2. Membuat Alat Python

### Langkah-langkah

1. **Setel variabel lingkungan `UAGENT_EXTERNAL_TOOLS_DIRS`** (jika belum disetel)

 Contoh:
 ```bash
   # Linux/macOS
   export UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
   # Windows (cmd)
   set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
   ```

 Beberapa direktori dapat dipisahkan dengan `:` (Linux/macOS) atau `;` (Windows).
 `UAGENT_EXTERNAL_TOOLS_DIR` (tunggal) juga didukung untuk kompatibilitas mundur.

2. **Buat file Python**

 Nama file gratis, tetapi disarankan untuk memberi nama `<name>_tool.py` (misalnya `my_tool.py`).

3. **Implementasikan elemen yang diperlukan**

 - kamus `TOOL_SPEC`
 - fungsi `run_tool(args)`
 - Opsional, file JSON i18n

4. **Restart agen** (atau jalankan alat `system_reload`)

### Templat Lengkap

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

Lihat [Bagian 5](#5-internasionalisasi-i18n) untuk detail i18n.

---

## 3. Membuat Alat Rust + Python

Implementasi Rust sangat ideal untuk tugas-tugas yang kritis terhadap kinerja (pemrosesan data berat, kriptografi, pemrosesan file, dll.).
uag dapat memuat file `.pyd` yang sudah dibuat sebelumnya secara langsung, sehingga **pengguna akhir tidak memerlukan `pip install`**.

### Struktur Alat

Alat Rust terdiri dari yang berikut file:

```
my_rust_tool/
├── Cargo.toml          # Rust project definition
├── pyproject.toml      # maturin build definition (build-time only)
├── src/
│   └── lib.rs          # Rust implementation
└── my_rust_tool.pyd    # Build artifact (ship with distribution)
```

Untuk distribusi, tempatkan file `_tool.py` + `_tool.json` + `.pyd` di
`UAGENT_EXTERNAL_TOOLS_DIRS`.

### Langkah

#### Langkah 1: Buat proyek Rust

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

#### Langkah 2: Implementasi Rust (src/lib.rs)

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

**Poin penting:**
- Ekspos fungsi dengan `#[pyfunction(name = "run_<name>")]`
- Jenis pengembalian adalah `PyResult<String>`
- Nama fungsi `#[pymodule]` harus cocok dengan nama peti (`my_rust_tools`)

#### Langkah 3: Bangun

```bash
cd my_rust_tool
cargo build --release
```

Windows: ganti nama `target/release/my_rust_tools.dll` menjadi `my_rust_tools.pyd`
Linux: ganti nama `target/release/libmy_rust_tools.so` menjadi `my_rust_tools.so`
macOS: ganti nama `target/release/libmy_rust_tools.dylib` menjadi `my_rust_tools.so`

Atau menggunakan maturin:
```bash
pip install maturin     # build-time only
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
```

#### Langkah 4: Buat pembungkus Python

Buat `my_rust_tool.py` di `UAGENT_EXTERNAL_TOOLS_DIRS` Anda direktori:

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

**``load_rust_pyd()`` urutan resolusi:**

1. Cari `<module_name>.pyd` (atau `.so`) di direktori yang sama dengan pembungkus `.py`
2. Kembali ke modul yang diinstal pip

#### Langkah 5: Distribusi

Hanya 3 file ini yang diperlukan. Pengguna akhir **tidak** memerlukan `pip install`.

```
my_rust_tool.py         # Python wrapper (TOOL_SPEC + run_tool)
my_rust_tool.json       # i18n translations (optional)
my_rust_tools.pyd       # Pre-built native binary
```

### Catatan

- **Hanya waktu pembuatan:** Rust toolchain dan `maturin` diperlukan
 ```bash
  pip install maturin
  ```
- The Rust nama peti (`[lib] name` di `Cargo.toml`) harus cocok dengan argumen pertama `load_rust_pyd()`
- Nama file wrapper dan lokasi `.pyd` bersifat independen selama keduanya berada di direktori yang sama

---

## 4. TOOL_SPEC Referensi

### Dasar Struktur

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

### Properti

| Bidang | Ketik | Deskripsi |
|-------|------|-------------|
| `ketik` | str | Selalu `"fungsi"` |
| `x_build` | str | `"rust"` untuk implementasi Rust (hilangkan untuk Python) |
| `alat_genre` | str | Nama genre (opsional). Mengaktifkan kontrol berbasis genre |
| `tingkat_alat` | ke dalam | 0=diaktifkan, 1=bersyarat (default), -1=dinonaktifkan |
| `fungsi.nama` | str | **Diperlukan**. Nama alat (huruf kecil + angka + garis bawah) |
| `fungsi.deskripsi` | str | **Diperlukan**. Deskripsi |
| `fungsi.x_search_terms` | daftar[str] | kata kunci penelusuran i18n-aware (dibungkus dengan `_(...)`) |
| `fungsi.x_search_terms_en` | daftar[str] | Memperbaiki kata kunci pencarian bahasa Inggris |
| `fungsi.parameter` | dikte | Definisi parameter (format pemanggilan fungsi OpenAI) |

---

## 5. Internasionalisasi (i18n)

### Mekanisme Penerjemahan

Memanggil `make_tool_translator(__file__)` memuat terjemahan dari file `.json`
dengan nama dasar yang sama di file yang sama direktori.

```python
from uagent.tools.i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)
```

### Menggunakan Tombol Terjemahan

```python
description = _(
    "tool.description",                          # Key name
    default="Default English text",              # Fallback value
)
```

### Format File JSON

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

Lihat yang ada File `_tool.json` untuk kode bahasa yang didukung.

---

## 6. Pengujian dan Debugging

### Pemeriksaan Sintaks

```bash
python -m py_compile my_tool.py
```

### Alat Verifikasi Memuat

```python
from uagent.tools import _RUNNERS, reload_plugins
reload_plugins()

if "my_tool" in _RUNNERS:
    result = _RUNNERS["my_tool"]({"input": "test"})
    print(result)
```

### Log Kesalahan

Kesalahan selama pemuatan alat dicetak ke stderr. Jika alat Anda tidak dimuat,
periksa log startup uag.

---

## 7. Contoh Referensi

### Contoh Alat Python

- `date_calc_tool.py` (dalam `src/uagent/tools/`) — Penghitungan tanggal. Salin secara eksternal dan sesuaikan.
- `calculator_tool.py` (di `src/uagent/tools/`) — Kalkulator.

### Contoh Alat Karat

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (di `src/uagent/tools_rust/`) — UUID generation
- `rust_slugify_tool.py` + `uag_tools_rust.pyd` (di `src/uagent/tools_rust/`) — Konversi slug

Salin file `_tool.py` dan `.pyd` ke `UAGENT_EXTERNAL_TOOLS_DIRS` untuk menggunakannya sebagai eksternal tools.

### Menyiapkan Direktori Alat Eksternal

```bash
# Linux/macOS
export UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools

# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path\to\my\tools;C:\path\to\other\tools

# Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Beberapa direktori dapat dipisahkan dengan `:` (Linux/macOS) atau `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (tunggal) juga didukung untuk kompatibilitas ke belakang.