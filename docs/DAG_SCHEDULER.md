# DAG-based Tool Scheduler

`uagent.runtime.dag_scheduler.run_dag()` executes dependency-aware Tool steps. Nodes whose dependencies are complete run concurrently; dependent nodes receive a dictionary of upstream results.

```python
from uagent.runtime.dag_scheduler import DagNode, run_dag

result = await run_dag([
    DagNode("fetch", fetch_data),
    DagNode("summarize", summarize, ("fetch",)),
])
```

Cycles, duplicate IDs, and missing dependencies raise `DagCycleError` before unsafe execution continues. Stable exception names and node IDs are machine-readable and are not localized; clients should translate only their user-facing presentation.

The scheduler is intentionally a small runtime primitive. Tool policy, confirmation, cancellation, and checkpoint persistence remain the responsibility of the caller until the full orchestration layer is enabled.
