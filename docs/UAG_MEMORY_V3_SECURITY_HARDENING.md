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

## Project authorization decision

The project boundary is now specified as **server-bound `ProjectContext` plus
server-side project membership policy**. A client-supplied `project_id` is only a
selector that must match the bound context; it is never an authorization grant.

Implementation requirements:

- derive WebSocket projects from the authenticated workspace/`TurnContext`;
- derive HTTP projects from the authenticated workspace or a configured single-project
  deployment, failing closed when no binding exists;
- add project memberships with `viewer` / `editor` / `admin` roles and generations;
- require project membership before room membership, audience, or per-record grants;
- bind rooms to exactly one project and invalidate snapshots/continuations on policy
  changes;
- use AD/Entra groups only as a policy source, never as ownership keys.

The current implementation now provides SQLite project memberships, role checks,
configured single-project binding, project membership APIs, and regression coverage.
HTTP ProjectContext is now server-bound for OIDC sessions through the
`/api/project-context` selection endpoint; configured single-project deployments
continue to use `UAGENT_MEMORY_PROJECT`. Room-to-project binding is persisted and
enforced at HTTP and Memory Projection boundaries. A trusted directory group policy
adapter now maps verified groups to Project/Room roles without storing raw group claims.
Workspace-derived project selection for non-OIDC/multi-project deployments remains a
follow-up.

## Current baseline

The main branch already provides identity/turn contexts, OIDC session binding,
SQLite audience/grant primitives, room roles, basic Personal/Room APIs, and safe
authentication status APIs. This document tracks the remaining hardening work; it
is intentionally separate from the architecture design document so the design
can remain stable while implementation proceeds.
