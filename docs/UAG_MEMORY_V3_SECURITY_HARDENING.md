# Memory v3 security hardening

## Scope

This follow-up hardens the gaps found by comparing `docs/UAG_MEMORY_ARCHITECTURE_V3.md`
with the current implementation.

## Work log

- [ ] Make project authorization server-controlled rather than trusting an arbitrary
  request `project_id`.
- [x] Re-check memory access generation before provider calls, streamed response
  delivery, and tool-loop continuation; revoked output is removed from the active
  Web room history and auto-pilot continuation is skipped.
- [x] Expose the existing revision-bound read-grant store through the documented
  `/api/me/shared-memories` and grant-management APIs.
- [ ] Add regression tests for project isolation and invalidation during an active
  turn; grant lifecycle coverage is now present in `tests/test_memory_v3_web_api.py`.
- [ ] Reconcile the configuration examples and mark remaining admin/AD features as
  implemented or roadmap items.

## Decision required before project hardening

The current Web API accepts a project identifier because the architecture document does
not yet define a project membership/policy source for HTTP requests. The next project
hardening change must choose one of these explicit contracts before changing behavior:

1. derive the project only from a server-bound `TurnContext`/workspace, or
2. add a server-side project policy (including the AD/Entra group mapping source).

Until that decision is implemented, callers must not treat a client-supplied
`project_id` as an authorization grant. The current hardening branch records this as
an open security item rather than silently inventing a policy.

## Current baseline

The main branch already provides identity/turn contexts, OIDC session binding,
SQLite audience/grant primitives, room roles, basic Personal/Room APIs, and safe
authentication status APIs. This document tracks the remaining hardening work; it
is intentionally separate from the architecture design document so the design
can remain stable while implementation proceeds.
