# Scoped management session metadata API (v1)

The existing management manifest credential (`UAGENT_MANAGEMENT_API_TOKEN`) remains **manifest-only**. Session metadata requires its **own** secret and an explicit server-side identity/project scope.

Set these only in the UAG Web service's private secret environment:

- `UAGENT_MANAGEMENT_READ_TOKEN`: independent random secret, at least 32 UTF-8 bytes.
- `UAGENT_MANAGEMENT_READ_PRINCIPAL`: trusted UAG principal for which session metadata is requested.
- `UAGENT_MANAGEMENT_READ_PROJECT_ID`: exact UAG project ID to permit.

The configured principal must have an **explicit, active, non-directory** `viewer` / `editor` / `admin` membership in the named active project under UAG's `ProjectAccessPolicy`. Cached directory-policy memberships are deliberately rejected because this bearer request has no authenticated directory identity with which to refresh revoked group access. Being listed in `UAGENT_ADMIN_PRINCIPALS` alone does **not** grant this service access: an explicit project membership is still required. No principal/project identity is accepted from the bearer caller. The endpoint additionally limits sessions to records whose `sessions.project` **and** `sessions.principal_id` exactly match those fixed settings. Existing sessions whose stored project label does not match the UAG project ID will not be returned. This conservative limit is intentional: project membership alone must not expose another user's private-room session metadata.

After setting the values and enabling the session store, the manifest advertises `session.metadata.read`.

```http
GET /api/admin/integration/v1/sessions?project_id=<exact-project-id>&limit=50
Authorization: Bearer <separate-read-token>
```

Only the session ID, project ID, `recorded` state and UTC creation/update times are returned. No conversation text, instruction, summary, room ID, path or message content is selected. Response includes `api_version: "1"`, `instance_id`, `items` and an opaque `next_cursor` for pagination (up to 100 items per page).

Unconfigured reads return 404, malformed configuration returns 503, missing/wrong bearer returns 401, project mismatch or denied membership returns 403, and invalid cursors return 400. A database or policy outage fails closed. The authorization database is opened with SQLite `mode=ro` for every read, without triggering MemoryStore schema initialization/migrations or modifying permissions. If the access database is absent, the API denies the request. Project membership can be provisioned/revoked via existing trusted project administration APIs. This credential does not authorize user/admin UAG endpoints or project membership writes.

The task history store does not yet provide a guaranteed project ownership key, so **no task-history capability** is advertised in this phase. The API is opt-in and disabled by default.

## Project membership metadata (read only)

When the independent management read credential is configured, the manifest
advertises `project.membership.read`. The fixed service principal must have an
explicit, active **admin** membership in the configured active project. Neither
`UAGENT_ADMIN_PRINCIPALS` nor a cached directory-policy membership can replace
that grant.

```http
GET /api/admin/integration/v1/projects/<configured-project-id>/members?limit=50
Authorization: Bearer <separate-read-token>
```

The response contains `api_version`, `instance_id`, `project_id`,
`members`, and `next_cursor`. Every member contains only `principal_id`,
`role` and `revision`. Pagination is sorted by principal ID and limited to
100 items per request. The opaque-in-purpose `cursor` equals the previous
page's final principal ID and does not grant access.

Directory-policy rows reflect the last trusted directory sync and may become
stale; this endpoint does not claim to refresh directory authorization. The
SQLite store is opened read-only, and the endpoint cannot write permissions.
Failures are fail-closed: absent read config 404, malformed config 503,
invalid bearer 401, unauthorized project/admin 403, and database failure 503.
No UAG Admin screen or permission-writing API is added in this phase.
