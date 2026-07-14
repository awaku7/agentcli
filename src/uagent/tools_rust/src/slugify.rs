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

    // Split into words: alphanumeric (ASCII) and non-ASCII (e.g. Japanese)
    // characters are kept; everything else (punctuation, whitespace) acts as
    // a word boundary.
    let mut words: Vec<String> = Vec::new();
    let mut current = String::new();

    for c in text.to_lowercase().chars() {
        if c.is_ascii_alphanumeric() || !c.is_ascii() {
            current.push(c);
        } else {
            // Punctuation / whitespace → word boundary
            if !current.is_empty() {
                words.push(current.clone());
                current.clear();
            }
        }
    }
    if !current.is_empty() {
        words.push(current);
    }

    Ok(words.join(&separator))
}
