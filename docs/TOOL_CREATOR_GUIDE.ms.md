# Panduan Pencipta Alat

Panduan ini menerangkan cara menambahkan alatan anda sendiri pada uag **tanpa mengubah suai uag itu sendiri**.
Jika anda ingin menambah alat terus pada pepohon sumber uag, lihat
\[DEVELOP_TOOL.md\](src/uagent/docs/DEVELOP_TOOL.md##\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Jadual Kandungan
\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_).
. [Quick Start: Scaffold Command](#0-quick-start-scaffold-command)

1. [Struktur Alat Asas](#1-struktur-alat-asas)
1. [Mencipta Alat Python](#2-creating-a-python-tool)
1. [Mencipta Alat Rust + Python](#3-creating-a-rust--python-tool)
1. \[Rujukan TOOL_SPEC\](#4-rujukan_spesifikasi alat)
1. [Pengantarabangsaan (i18n)](#5-pengantarabangsaan-i18n)
1. [Pengujian dan Nyahpepijat](#6-pengujian-dan-nyahpepijat)
1. [Contoh Rujukan](#7-rujukan-contoh)

______________________________________________________________________

## 0. Permulaan Pantas: Perintah Scaffold

Cara paling mudah untuk mencipta alat baharu ialah menggunakan perintah **`:tool create`**
daripada gesaan CLI. Ia menjana fail boilerplate secara automatik.

### Penggunaan

```
:tool create <name> --lang python|rust [--description '...'] [--output-dir <dir>]
```

| Hujah | Diperlukan | Penerangan |
|----------|----------|-------------|
| `<nama>` | Ya | Nama alat (cth., `my_search`, `file_processor`) |
| `--lang` | Tidak | `python` (lalai) atau `karat` |
| `--penerangan` | Tidak | Penerangan ringkas tentang alat |
| `--output-dir` | Tidak | Direktori output (lalai: laluan pertama dalam `UAGENT_EXTERNAL_TOOLS_DIRS`, atau direktori semasa) |

### Contoh

```teks
# Python tool
:tool create my_search --lang python --description "Alat carian tersuai"
# Rust tool
:tool -heavy-langkarat data pemproses"
```

### What Gets Generated

**Python (`--lang python`)**:

- `<name>_tool.py` — Pelaksanaan alat dengan `TOOL_SPEC` dan `run_tool()`
- `<name>_tool.json` — templat terjemahan i18n. sudah sedia untuk digunakan
  Letakkannya dalam `UAGENT_EXTERNAL_TOOLS_DIRS`
  anda dan mulakan semula ejen (atau jalankan `system_reload`).
  **Rust (`--lang rust`)**:
- `<name>/` — Direktori projek kargo dengan `Cargo.toml`, `pyproject.toml`, dan .`pyproject.toml` dan .` `<name>\_tool.py`— Pembalut Python yang memuatkan`.pyd\`
  Selepas perancah, bina dan pasang:

```bash
cd <name>
maturin build --release
pip install target/wheels/*.whl
```

Then build in`py. anda `UAGENT_EXTERNAL_TOOLS_DIRS\` dan mulakan semula ejen.

______________________________________________________________________

## 1. Struktur Alat Asas

Alat terdiri daripada elemen berikut:
| Elemen | Diperlukan | Penerangan |
|---------|----------|-------------|
| `TOOL_SPEC` | Ya | Kamus mentakrifkan nama alat, perihalan dan parameter |
| `run_tool(args)` | Ya | Fungsi dilaksanakan apabila alat dipanggil. Args ialah dict, return adalah rentetan. |
| i18n JSON | Disyorkan | Terjemahan JSON fail (nama asas yang sama, `<name>_tool.json`) |

### Minimal Python Tool

```python
# my_tool.py
daripada menaip import Any
def run_tool(args: dict[str, Any]) -> str:
 name = args.,
 name = args. {name}!"
TOOL_SPEC: dict[str, Any] = {
 "type": "function",
 "x_parallel_safe": Benar, # Selamat untuk dijalankan serentak apabila True
 "function": {
 "name": "my_tool",
 "description": "Saystypello": "Saystypello": "Saystypello". "objek",
 "sifat": {
 "nama": {
 "jenis": "rentetan",
 "penerangan": "Nama untuk disambut",
 },
 },
 },
 },
}
```

______________________________________________________________________

## Langkah 2. Mencipta a. **Tetapkan pembolehubah persekitaran `UAGENT_EXTERNAL_TOOLS_DIRS`** (jika belum ditetapkan)

Contoh:

```bash
# Linux/macOS
eksport UAGENT_EXTERNAL_TOOLS_DIRS=~/.uag/my_tools
# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=%USERPROFILE%\.uag\my_tools
```

Berbilang direktori boleh dipisahkan oleh `:` (Linux/macOS) atau `;` (Windows).
`UAGENT_EXTERNAL_TOOLS_DIR` (disokong ke belakang⎏1). **Buat fail Python**
Nama fail adalah percuma, tetapi penamaan `<name>_tool.py` disyorkan (cth. `my_tool.py`).

1. **Laksanakan elemen yang diperlukan**

- Kamus `TOOL_SPEC`
- fungsi `run_tool(args)`
- Secara pilihan, fail i18n JSON

1. **Mulakan semula ejen** (atau jalankan alat `system_reload`)

### Templat Penuh

```python
daripada anotasi import __future__
daripada menaip import Mana
daripada uagent.tools.i18n_helper import make_tool_translator
_(make_deftool_translator
_ = make_def_tool_translator
_ = make_def_tool_translator dict[str, Any]) -> str:
 """Laksanakan alat."""
 input_text = args.get("input", "")
 result = f"Diproses: {input_text}"
 return result
TOOL_SPEC: dict[str, Any] = {
"type": "function", "type": "function "my_tool",
 "description": _(
 "tool.description",
 default="Description of my_tool",
 ),
 "x_search_terms": _(
 "x_search_terms",
 default=["my_tool", "keyword1"],
 ),
 "en_",:_keyword"] "parameters": {
 "type": "object",
 "properties": {
 "input": {
 "type": "string",
 "description": _("param.input", default="Input text"),
 },
 },
 },
}

`Bahagian `,
 
 5](#5-pengantarabangsaan-i18n) untuk butiran i18n.
________________________________________________________________________________
## 3. Mencipta Alat Rust + Python
Pelaksanaan Rust sesuai untuk tugas kritikal prestasi (pemprosesan data berat, kriptografi, pemprosesan fail, dsb.).
uag boleh memuatkan terus fail `.spyd`perluan pengguna `, dontpi's `psyp` terbina pra-bina. install`**.
### Struktur Alat
Alat Rust terdiri daripada fail berikut:
```

my_rust_tool/
├── Cargo.toml # Rust project definition
├── pyproject.toml # maturin build definition (masa binaan sahaja)
┎── src └── lib.rs # Pelaksanaan karat
└── my_rust_tool.pyd # Bina artifak (kapalkan dengan pengedaran)

````
Untuk pengedaran, letakkan fail `_tool.py` + `_tool.json` + `.pyd` dalam
#DINAL_TO_EXTER. Langkah
#### Langkah 1: Cipta projek Rust
**Cargo.toml**
```toml
[pakej]
name = "my_rust_tools"
version = "0.1.0"
edition = "2021"
[lib]
name = "my_rust_crates" ["cdylib"]
[dependencies]
pyo3 = { version = "0.29", features = ["extension-module", "abi3-py311"] }
````

**pyproject.toml**

```toml
[build-system]
requires = ["0.backend]=1 "maturin"]
[projek]
name = "my_rust_tools"
version = "0.1.0"
requires-python = ">=3.11"
```

#### Langkah 2: Pelaksanaan karat (src/lib.rs)

````rust
use
```rust
use pyo3::*:prelude pyo3 std::collections::HashMap;
#[pyfunction(name = "run_my_operation")]
pub fn run(args: HashMap<String, Py<PyAny>>) -> PyResult<String> {
 let py = unsafe { Python::
 input_attached() = }tgs;
 .get("input")
 .and_then(|v: &Py<PyAny>| v.bind(py).extract::<String>().ok())
 .unwrap_or_default();
 biarkan hasil = format!("Rust berkata: {}", input);
# Ok[py}
]⎎ my_rust_tools(m: &Bound<'_, PyModule>) -> PyResult<()> {
 m.add_function(wrap_pyfunction!(run, m)?)?;
 Ok(())
}
````

**Mata penting:**

- "#nama_jalin" = ``` [nama_] = Dedahkan fungsi dengan ``] Jenis pulangan ialah  ```PyResult<String>\`
- Nama fungsi `#[pymodule]` mesti sepadan dengan nama peti (`my_rust_tools`)

#### Langkah 3: Build

````bash
cd my_rust_tool
cargo build --release
```lename
my Windows kepada `my_rust_tools.pyd`
Linux: menamakan semula `target/release/libmy_rust_tools.so` kepada `my_rust_tools.so`
macOS: menamakan semula `target/release/libmy_rust_tools.dylib` kepada `my_rust_tools.so``
Or install menggunakan matur``
Or install` masa bina sahaja
maturin build --release
# Extract .pyd/.so from target/wheels/*.whl
````

#### Langkah 4: Buat pembungkus Python

Cipta `my_rust_tool.py` dalam direktori `UAGENT_EXTERNAL_TOOLS_DIRS` anda:

```python
daripada anotasi import __future__
daripada menaip import Mana
daripada uagent.tools.i18n_helper import make_f.rom_translator__.PH_helper import make_f_roms_translator__PH_helper load_rust_pyd
_ = make_tool_translator(__file__)
# Letakkan .pyd dalam direktori yang sama — auto-detected
_rust_mod = load_rust_pyd("my_rust_tools")
run_tool = _rust_mod.run_my_operation
TOOL_TRPEC: Any "[spesies]" "function",
 "x_build": "rust",
 "function": {
 "name": "my_operation",
 "description": _("tool.description", default="My Rust operation"),
 "x_search_terms": _("x_search_terms", default=["my_operation"]": [_terms"s_my_operation]": [_terms"s_my_operation]": 
_terms_my_my "parameters": {
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

**`load_rust_pyd()` tertib peleraian:**

1. Cari `<module_name>.pyd` (atau `.so`) dalam direktori yang sama dengan pembalut `.py`
1. Kembali ke modul yang dipasang pip

#### Langkah 5: Pengedaran

Hanya 3 fail ini diperlukan. Pengguna akhir **tidak** memerlukan sebarang `pemasangan pip`.

````
my_rust_tool.py # Pembalut Python (TOOL_SPEC + run_tool)
my_rust_tool.json # terjemahan i18n (pilihan)
my_rust_tools.pyd # Pre-built native binary
`##`*Nota binari asli
`##`*
`##`* rantai alat dan `maturin` diperlukan
 ```bash
 pip install maturin
````

- Nama peti Rust (nama `[lib]` dalam `Cargo.toml`) mesti sepadan dengan hujah pertama `load_rust_pyd()`
- Nama fail pembungkus dan `.pyd` berada di lokasi yang sama direktori

______________________________________________________________________

## 4. Rujukan TOOL_SPEC

### Struktur Asas

```python
TOOL_SPEC: dict[str, Any] = {
 "type": "function", # Fixed
 "x_build": "rust", # "Hanya untuk pelaksanaan Rustity" (pilihan)
 "peringkat_alat": 0, # 0=didayakan, 1=bersyarat, -1=dilumpuhkan
 "fungsi": {
 "nama": "nama_alat", # Nama alat (snake_case)
 "penerangan": "...", # Perihalan
 "x_search_terms": [...], # Kata kunci carian "i_1_0": [...], # Kata kunci carian "x_0": 8n
 [...], # kata kunci carian Bahasa Inggeris (tetap)
 "parameter": {
 "jenis": "objek",
 "sifat": {
 "param1": {
 "jenis": "rentetan",
 "penerangan": "...",
 },
 "param2": {
 "jenis": {
 "jenis": {
 "jenis",
 "enum": [1, 2, 3],
 },
 },
 "diperlukan": ["param1"],
 },
 },
}
```

### Properties

| Medan | Taip | Penerangan |
|-------|------|-------------|
| `jenis` | str | Sentiasa `"fungsi"` |
| `x_build` | str | `"karat"` untuk pelaksanaan Rust (tinggalkan untuk Python) |
| `genre_alat` | str | Nama genre (pilihan). Mendayakan kawalan berasaskan genre |
| `peringkat_alat` | int | 0=didayakan, 1=bersyarat (lalai), -1=dilumpuhkan |
| `x_parallel_safe` | bool | Sama ada panggilan bebas boleh dijalankan serentak |
| `function.name` | str | **Diperlukan**. Nama alat (huruf kecil + digit + garis bawah) |
| `function.description` | str | **Diperlukan**. Penerangan |
| `fungsi.x_search_terms` | senarai[str] | Kata kunci carian i18n-aware (balut dengan `_(...)`) |
| `function.x_search_terms_en` | senarai[str] | Kata kunci carian bahasa Inggeris tetap |
| `function.parameters` | dict | Takrifan parameter (Format panggilan fungsi OpenAI) |

______________________________________________________________________

## 5. Pengantarabangsaan (i18n)

### Mekanisme Terjemahan

Panggilan `make_tool_translator(__file__)` memuatkan terjemahan daripada fail `.json`
dengan nama asas yang sama dalam direktori yang sama.
`romthon ` uagent.tools.i18n_helper import make_tool_translator
\_ = make_tool_translator(__file__)

````
### Menggunakan Kekunci Terjemahan
```python
description = _(
 "tool.description", # Key name
 default="#``back English text⎎", # Fa
 JSON Format Fail
```json
{
 "en": {
 "tool.description": "Default English text",
 "param.input": "Input text"
 },
 "ja": {
 "tool.description": "日本語の誇m",明掏"入力テキスト"
 }
}
````

Lihat fail `_tool.json` sedia ada untuk kod bahasa yang disokong.

______________________________________________________________________

## 6. Menguji dan Menyahpepijat

### Semakan Sintaks

```thbash
 -m pyly my_tool.py
```

### Sahkan Pemuatan Alat

```python
daripada uagent.tools import _RUNNERS, reload_plugins
reload_plugins()
jika "my_tool" dalam _RUNNERS:
 result = _RUNNERS:
 result = _RUNNERS""put ["{"}tools] cetak(hasil)
```

### Log Ralat

Ralat semasa pemuatan alat dicetak ke stderr. Jika alat anda tidak dimuatkan,
semak log permulaan uag.

______________________________________________________________________

## 7. Contoh Rujukan

### Contoh Alat Python

- `date_calc_tool.py` (dalam `src/uagent/tools/`) — Pengiraan tarikh. Salin secara luaran dan sesuaikan.
- `calculator_tool.py` (dalam `src/uagent/tools/`) — Kalkulator.

### Contoh Alat Karat

- `rust_uuid_gen_tool.py` + `uag_tools_rust.pyd` (dalam `src/uagent/`)tools `rust_slugify_tool.py` + `uag_tools_rust.pyd` (dalam `src/uagent/tools_rust/`) — Penukaran slug
  Salin fail `_tool.py` dan `.pyd` ke dalam `UAGENT_EXTERNAL_TOOLS_DIRS` untuk menggunakannya sebagai Alat Luar### Tetapan.
  Direktori

```bash
# Linux/macOS
eksport UAGENT_EXTERNAL_TOOLS_DIRS=/path/to/my/tools:/path/to/other/tools
# Windows (cmd)
set UAGENT_EXTERNAL_TOOLS_DIRS=C:\path;to⎉my:\path;to\my Windows (PowerShell)
$env:UAGENT_EXTERNAL_TOOLS_DIRS = "C:\path\to\my\tools;C:\path\to\other\tools"
```

Berbilang direktori boleh dipisahkan oleh `:` (Linux/macOS) atau `;`TER_DIRO_Windows. (tunggal) juga disokong untuk keserasian ke belakang.
