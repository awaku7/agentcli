# Memory v3 security hardening

## Scope

This follow-up hardens the gaps found by comparing `docs/UAG_MEMORY_ARCHITECTURE_V3.md`
with the current implementation.

## Work log

- [ ] Make project authorization server-controlled rather than trusting an arbitrary
  request `project_id`.
- [ ] Re-check memory access generation before provider calls, streamed response
  delivery, and tool-loop continuation.
- [x] Expose the existing revision-bound read-grant store through the documented
  `/api/me/shared-memories` and grant-management APIs.
- [ ] Add regression tests for project isolation and invalidation during an active
  turn; grant lifecycle coverage is now present in `tests/test_memory_v3_web_api.py`.
- [ ] Reconcile the configuration examples and mark remaining admin/AD features as
  implemented or roadmap items.

## Current baseline

The main branch already provides identity/turn contexts, OIDC session binding,
SQLite audience/grant primitives, room roles, basic Personal/Room APIs, and safe
authentication status APIs. This document tracks the remaining hardening work; it
is intentionally separate from the architecture design document so the design
can remain stable while implementation proceeds.
