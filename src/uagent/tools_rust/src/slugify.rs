use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;

#[pyfunction(name = "run_slugify")]
pub fn run(args: HashMap<String, Py<PyAny>>) -> PyResult<String> {
    let py = unsafe { Python::assume_attached() };

    let text: String = args
        .get("text")
        .and_then(|v: &Py<PyAny>| v.bind(py).extract::<String>().ok())
        .ok_or_else(|| PyValueError::new_err("text is required"))?;

    let separator: String = args
        .get("separator")
        .and_then(|v: &Py<PyAny>| v.bind(py).extract::<String>().ok())
        .unwrap_or_else(|| "-".to_string());

    if text.is_empty() {
        return Ok(String::new());
    }

    let slug: String = text
        .to_lowercase()
        .chars()
        .map(|c: char| {
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
