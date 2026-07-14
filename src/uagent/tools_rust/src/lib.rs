use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::*;
use std::collections::HashMap;

// ── Helper ───────────────────────────────────────────────────────

fn _py_err(msg: &str) -> PyErr {
    PyValueError::new_err(msg.to_string())
}

fn _build_spec(
    py: Python<'_>,
    name: &str,
    description: &str,
    params: &[(&str, &str, &str)],
    required: &[&str],
    search_terms: &[&str],
) -> PyResult<PyObject> {
    let spec = PyDict::new(py);
    let function = PyDict::new(py);

    function.set_item("name", name)?;
    function.set_item("description", description)?;

    let parameters = PyDict::new(py);
    let properties = PyDict::new(py);

    for (pname, ptype, pdesc) in params {
        let prop = PyDict::new(py);
        prop.set_item("type", ptype)?;
        prop.set_item("description", pdesc)?;
        properties.set_item(pname, prop)?;
    }

    parameters.set_item("type", "object")?;
    parameters.set_item("properties", properties)?;
    if !required.is_empty() {
        parameters.set_item("required", required)?;
    }

    function.set_item("parameters", parameters)?;

    let terms: Vec<&str> = search_terms.to_vec();
    function.set_item("x_search_terms", terms)?;
    function.set_item("x_search_terms_en", search_terms.to_vec())?;

    spec.set_item("type", "function")?;
    spec.set_item("tool_genre", "utility")?;
    spec.set_item("tool_level", 0)?;
    spec.set_item("function", function)?;

    Ok(spec.into())
}

// ── Tool 1: uuid_gen ─────────────────────────────────────────────

#[pyfunction]
fn run_uuid_gen(args: HashMap<String, PyObject>) -> PyResult<String> {
    let py = unsafe { Python::assume_gil_acquired() };

    let count: usize = args
        .get("count")
        .and_then(|v| v.extract::<usize>(py).ok())
        .unwrap_or(1);

    if count == 0 || count > 100 {
        return Err(_py_err("count must be between 1 and 100"));
    }

    let mut result = Vec::with_capacity(count);
    for _ in 0..count {
        let u = uuid::Uuid::new_v4();
        result.push(u.to_string());
    }
    Ok(result.join("\n"))
}

fn _uuid_spec(py: Python<'_>) -> PyResult<PyObject> {
    _build_spec(
        py,
        "uuid_gen",
        "Generate one or more UUID v4 strings. Returns one per line.",
        &[(
            "count",
            "integer",
            "Number of UUIDs to generate (1-100, default 1)",
        )],
        &[],
        &["uuid", "uuid_gen", "generate uuid", "guid"],
    )
}

// ── Tool 2: slugify ──────────────────────────────────────────────

#[pyfunction]
fn run_slugify(args: HashMap<String, PyObject>) -> PyResult<String> {
    let py = unsafe { Python::assume_gil_acquired() };

    let text: String = args
        .get("text")
        .and_then(|v| v.extract::<String>(py).ok())
        .ok_or_else(|| _py_err("text is required"))?;

    let separator: String = args
        .get("separator")
        .and_then(|v| v.extract::<String>(py).ok())
        .unwrap_or_else(|| "-".to_string());

    if text.is_empty() {
        return Ok(String::new());
    }

    let slug: String = text
        .to_lowercase()
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() {
                c
            } else if c.is_whitespace() || c == '-' || c == '_' {
                '-'
            } else {
                ' '
            }
        })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<&str>>()
        .join(&separator);

    Ok(slug)
}

fn _slugify_spec(py: Python<'_>) -> PyResult<PyObject> {
    _build_spec(
        py,
        "slugify",
        "Convert text to a URL-friendly slug (e.g. 'Hello World' -> 'hello-world').",
        &[
            ("text", "string", "Text to convert to a slug"),
            ("separator", "string", "Word separator (default: '-')"),
        ],
        &["text"],
        &["slugify", "slug", "url slug", "text to slug"],
    )
}

// ── Module definition ────────────────────────────────────────────

#[pymodule]
fn tools_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Runner functions
    m.add_function(wrap_pyfunction!(run_uuid_gen, m)?)?;
    m.add_function(wrap_pyfunction!(run_slugify, m)?)?;

    let py = m.py();

    // Tool 1: uses TOOL_SPEC + run_tool (default runner)
    m.add("TOOL_SPEC", _uuid_spec(py)?)?;
    m.add("run_tool", wrap_pyfunction!(run_uuid_gen, m)?)?;

    // Tool 2: uses TOOL_SPEC_3 + TOOL_SPEC_3_RUNNER
    m.add("TOOL_SPEC_3", _slugify_spec(py)?)?;
    m.add("TOOL_SPEC_3_RUNNER", wrap_pyfunction!(run_slugify, m)?)?;

    Ok(())
}
