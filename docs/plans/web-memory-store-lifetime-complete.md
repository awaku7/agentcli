# Web Memory store lifetime follow-up

Status: implemented in `fix/web-memory-store-lifetime`.

The v0.7.14 review identified a denied-request path where a Web Memory SQLite store could be opened before authorization completed and therefore never reach the caller's explicit `finally: store.close()` block.

The fix adds request-local MemoryStore tracking in `web_impl/app.py`, regression coverage for denied Personal/Room Memory requests, and updates developer documentation. This file is intentionally short and may be removed or folded into the implementation roadmap after merge.
