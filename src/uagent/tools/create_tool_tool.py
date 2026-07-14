from __future__ import annotations

import os
import re
from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "",
    "function": {
        "name": "create_tool",
        "description": _(
            "tool.description",
            default="Scaffold a new tool (Python or Rust+Python) with boilerplate files.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["create tool", "scaffold", "new tool", "tool template"],
        ),
        "x_search_terms_en": [
            "create tool",
            "scaffold",
            "new tool",
            "tool template",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name",
                        default="Tool name (snake_case, e.g. 'my_tool')",
                    ),
                },
                "lang": {
                    "type": "string",
                    "enum": ["python", "rust"],
                    "description": _(
                        "param.lang",
                        default="Implementation language: 'python' or 'rust'",
                    ),
                },
                "description": {
                    "type": "string",
                    "description": _(
                        "param.description",
                        default="Short description of what the tool does",
                    ),
                },
                "output_dir": {
                    "type": "string",
                    "description": _(
                        "param.output_dir",
                        default="Output directory (default: UAGENT_EXTERNAL_TOOLS_DIR or current dir)",
                    ),
                },
            },
            "required": ["name"],
        },
    },
}


def _validate_name(name: str) -> str | None:
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        return "Name must be snake_case, start with a letter, and contain only a-z, 0-9, underscore"
    return None


def _to_pascal(name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def _scaffold_python_tool(name: str, description: str, out_dir: str) -> list[str]:
    files_created = []
    tool_file = os.path.join(out_dir, f"{name}_tool.py")

    desc_short = description or f"A {name} tool"

    py_code = f'''from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def run_tool(args: dict[str, Any]) -> str:
    """Execute the tool."""
    # --- Your tool logic here ---
    input_text = args.get("input", "")
    result = f"Hello from {{input_text}}!" if input_text else "Hello from {name}!"
    return result


TOOL_SPEC: dict[str, Any] = {{
    "type": "function",
    "function": {{
        "name": "{name}",
        "description": _(
            "tool.description",
            default="{desc_short}",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["{name}"],
        ),
        "x_search_terms_en": ["{name}"],
        "parameters": {{
            "type": "object",
            "properties": {{
                "input": {{
                    "type": "string",
                    "description": _("param.input", default="Input text"),
                }},
            }},
        }},
    }},
}}
'''
    with open(tool_file, "w", encoding="utf-8") as f:
        f.write(py_code)
    files_created.append(tool_file)

    json_file = os.path.join(out_dir, f"{name}_tool.json")
    json_code = f'''{{
    "en": {{
        "tool.description": "{desc_short}",
        "x_search_terms": ["{name}"],
        "param.input": "Input text"
    }},
    "ja": {{
        "tool.description": "{desc_short}（日本語説明）",
        "x_search_terms": ["{name}"],
        "param.input": "入力テキスト"
    }}
}}
'''
    with open(json_file, "w", encoding="utf-8") as f:
        f.write(json_code)
    files_created.append(json_file)

    return files_created


def _scaffold_rust_tool(name: str, description: str, out_dir: str) -> list[str]:
    files_created = []
    rust_dir = os.path.join(out_dir, name)
    src_dir = os.path.join(rust_dir, "src")
    os.makedirs(src_dir, exist_ok=True)

    desc_short = description or f"A {name} tool"

    cargo_toml = f'''[package]
name = "{name}"
version = "0.1.0"
edition = "2021"

[lib]
name = "{name}"
crate-type = ["cdylib"]

[dependencies]
pyo3 = {{ version = "0.29", features = ["extension-module", "abi3-py311"] }}
'''
    cargo_path = os.path.join(rust_dir, "Cargo.toml")
    with open(cargo_path, "w", encoding="utf-8") as f:
        f.write(cargo_toml)
    files_created.append(cargo_path)

    lib_rs = f'''use pyo3::prelude::*;
use std::collections::HashMap;

#[pyfunction(name = "run_{name}")]
pub fn run(args: HashMap<String, Py<PyAny>>) -> PyResult<String> {{
    let py = unsafe {{ Python::assume_attached() }};

    let input: String = args
        .get("input")
        .and_then(|v: &Py<PyAny>| v.bind(py).extract::<String>().ok())
        .unwrap_or_default();

    let result = if input.is_empty() {{
        "Hello from {name}!".to_string()
    }} else {{
        format!("Hello from {{}}!", input)
    }};

    Ok(result)
}}

#[pymodule]
fn {name}(m: &Bound<'_, PyModule>) -> PyResult<()> {{
    m.add_function(wrap_pyfunction!(run, m)?)?;
    Ok(())
}}
'''
    lib_path = os.path.join(src_dir, "lib.rs")
    with open(lib_path, "w", encoding="utf-8") as f:
        f.write(lib_rs)
    files_created.append(lib_path)

    readme_path = os.path.join(rust_dir, "README.md")
    _readme_lines = [
        f"# {name}",
        "",
        desc_short,
        "",
        "## Build",
        "",
        "```bash",
        "maturin build --release",
        "pip install target/wheels/*.whl",
        "```",
        "",
    ]
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(_readme_lines))
    files_created.append(readme_path)

    pyproject_toml = f'''[build-system]
requires = ["maturin>=1.0"]
build-backend = "maturin"

[project]
name = "{name}"
version = "0.1.0"
description = "{desc_short}"
readme = "README.md"
requires-python = ">=3.11"
'''
    pyproject_path = os.path.join(rust_dir, "pyproject.toml")
    with open(pyproject_path, "w", encoding="utf-8") as f:
        f.write(pyproject_toml)
    files_created.append(pyproject_path)

    wrapper_file = os.path.join(out_dir, f"{name}_tool.py")
    wrapper_code = f'''from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# Import the compiled Rust module
# Build: cd {name} && maturin build --release && pip install target/wheels/*.whl
from {name} import run_{name} as run_tool  # noqa: E402

TOOL_SPEC: dict[str, Any] = {{
    "type": "function",
    "function": {{
        "name": "{name}",
        "description": _(
            "tool.description",
            default="{desc_short}",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["{name}"],
        ),
        "x_search_terms_en": ["{name}"],
        "parameters": {{
            "type": "object",
            "properties": {{
                "input": {{
                    "type": "string",
                    "description": _("param.input", default="Input text"),
                }},
            }},
        }},
    }},
}}
'''
    with open(wrapper_file, "w", encoding="utf-8") as f:
        f.write(wrapper_code)
    files_created.append(wrapper_file)

    json_file = os.path.join(out_dir, f"{name}_tool.json")
    json_code = f'''{{
    "en": {{
        "tool.description": "{desc_short}",
        "x_search_terms": ["{name}"],
        "param.input": "Input text"
    }},
    "ja": {{
        "tool.description": "{desc_short}（日本語説明）",
        "x_search_terms": ["{name}"],
        "param.input": "入力テキスト"
    }}
}}
'''
    with open(json_file, "w", encoding="utf-8") as f:
        f.write(json_code)
    files_created.append(json_file)

    return files_created


def run_tool(args: dict[str, Any]) -> str:
    name = args.get("name", "")
    lang = args.get("lang", "python")
    description = args.get("description", "")
    output_dir = args.get("output_dir", "")

    err = _validate_name(name)
    if err:
        return f"Error: {err}"

    if not output_dir:
        from uagent.env_utils import env_get
        _ext_dirs = (
            env_get("UAGENT_EXTERNAL_TOOLS_DIRS")
            or env_get("UAGENT_EXTERNAL_TOOLS_DIR")
            or ""
        )
        output_dir = _ext_dirs.split(os.pathsep)[0].strip() or os.getcwd()

    os.makedirs(output_dir, exist_ok=True)

    if lang == "python":
        files = _scaffold_python_tool(name, description, output_dir)
    elif lang == "rust":
        files = _scaffold_rust_tool(name, description, output_dir)
    else:
        return f"Error: unsupported language '{lang}'. Use 'python' or 'rust'."

    lines = [f"Created {len(files)} file(s) for '{name}' ({lang}):"]
    for f in files:
        lines.append(f"  {f}")

    if lang == "rust":
        lines.append("")
        lines.append("Next steps:")
        lines.append(f"  1. cd {os.path.join(output_dir, name)}")
        lines.append("  2. maturin build --release")
        lines.append("  3. pip install target/wheels/*.whl")
        lines.append(f"  4. Place {os.path.join(output_dir, name + '_tool.py')} in UAGENT_EXTERNAL_TOOLS_DIR")
        lines.append("  5. Restart the agent")

    lines.append("")
    lines.append("Don't forget to add i18n translations to the .json file!")

    return "\n".join(lines)


def _cmd_handler(arg: str, **kwargs: Any) -> str:
    """Handle :tool create <args>"""
    import shlex

    parts = shlex.split(arg)
    name = None
    lang = "python"
    description = ""
    output_dir = None

    i = 0
    while i < len(parts):
        p = parts[i]
        if p == "--lang" and i + 1 < len(parts):
            lang = parts[i + 1]
            i += 2
        elif p == "--description" and i + 1 < len(parts):
            description = parts[i + 1]
            i += 2
        elif p == "--output-dir" and i + 1 < len(parts):
            output_dir = parts[i + 1]
            i += 2
        elif name is None:
            name = p
            i += 1
        else:
            i += 1

    if not name:
        return "Usage: :tool create <name> --lang python|rust [--description '...'] [--output-dir <dir>]"

    args = {
        "name": name,
        "lang": lang,
        "description": description,
    }
    if output_dir:
        args["output_dir"] = output_dir

    return run_tool(args)


CMD_SPEC: dict[str, Any] = {
    "command": "tool",
    "subcommand": "create",
    "help_text": _(
        "cmd.help",
        default=":tool create <name> --lang python|rust --description '...'",
    ),
    "handler": _cmd_handler,
}
