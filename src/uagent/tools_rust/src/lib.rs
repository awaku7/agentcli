mod uuid_gen;
mod slugify;

use pyo3::prelude::*;

#[pymodule]
fn tools_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(uuid_gen::run, m)?)?;
    m.add_function(wrap_pyfunction!(slugify::run, m)?)?;
    Ok(())
}
