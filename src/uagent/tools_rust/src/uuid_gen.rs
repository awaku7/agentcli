use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;

#[pyfunction(name = "run_uuid_gen")]
pub fn run(args: HashMap<String, Py<PyAny>>) -> PyResult<String> {
    let py = unsafe { Python::assume_attached() };

    let count: usize = args
        .get("count")
        .and_then(|v| v.bind(py).extract::<usize>().ok())
        .unwrap_or(1);

    if count == 0 || count > 100 {
        return Err(PyValueError::new_err("count must be between 1 and 100"));
    }

    let mut result = Vec::with_capacity(count);
    for _ in 0..count {
        let u = uuid::Uuid::new_v4();
        result.push(u.to_string());
    }
    Ok(result.join("\n"))
}
