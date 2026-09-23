# Web Memory resource lifetime

This note documents the request-level lifetime rule for authenticated Web Memory.

`src/uagent/web_impl/routes_api.py` opens short-lived SQLite `MemoryStore` instances for Personal Memory, shared-memory grants, Project/Room membership, and Room Memory operations. Some authorization failures can occur after a store has been opened but before a route helper returns the handle to its caller.

To keep those denied/error paths bounded, `src/uagent/web_impl/app.py` tracks MemoryStore instances opened by Web API routes in a request-local `ContextVar` and closes them when the HTTP request finishes. Existing explicit `finally: store.close()` blocks remain valid; SQLite connection close is safe when the request-level cleanup encounters an already-closed handle.

The request tracker is intentionally scoped to Web API `open_memory_store` calls. It is a safety net rather than an authorization mechanism: Project/Room membership and Memory audience checks remain in `routes_api.py`, `runtime/project_access.py`, `runtime/room_access.py`, and `runtime/memory_access.py`.

Concurrency is isolated by `ContextVar`; one request never owns another request's store list.

Regression coverage: `tests/test_web_memory_store_lifetime.py` verifies cleanup after denied Personal Memory access and after denied Room Memory access when the room is not bound to the selected project.
