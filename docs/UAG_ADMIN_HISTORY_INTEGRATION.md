# Scoped management session metadata API (v1)

The existing management manifest credential (`UAGENT_MANAGEMENT_API_TOKEN`) remains **manifest-only**. Session metadata requires its **own** secret and an explicit server-side identity/project scope.

Set these only in the UAG Web service's private secret environment:

- `UAGENT_MANAGEMENT_READ_TOKEN`: independent random secret, at least 32 UTF-8 bytes.
- `UAGENT_MANAGEMENT_READ_PRINCIPAL`: trusted UAG principal for which session metadata is requested.
- `UAGENT_MANAGEMENT_READ_PROJECT_ID`: exact UAG project ID to permit.

The configured principal must have at least `viewer` membership in the named project under UAG's `ProjectAccessPolicy`. No principal/project identity is accepted from the bearer caller. The endpoint additionally limits sessions to records whose `sessions.project` **and** `sessions.principal_id` exactly match those fixed settings. Existing sessions whose stored project label does not match the UAG project ID will not be returned. This conservative limit is intentional: project membership alone must not expose another user's private-room session metadata.

After setting the values and enabling the session store, the manifest advertises `session.metadata.read`.

```http
GET /api/admin/integration/v1/sessions?project_id=<exact-project-id>&limit=50
Authorization: Bearer <separate-read-token>
```

Only the session ID, project ID, `recorded` state and UTC creation/update times are returned. No conversation text, instruction, summary, room ID, path or message content is selected. Response includes `api_version: "1"`, `instance_id`, `items` and an opaque `next_cursor` for pagination (up to 100 items per page).

Unconfigured reads return 404, malformed configuration returns 503, missing/wrong bearer returns 401, project mismatch or denied membership returns 403, and invalid cursors return 400. A database or policy outage fails closed. This credential does not authorize user/admin UAG endpoints or project membership writes.

The task history store does not yet provide a guaranteed project ownership key, so **no task-history capability** is advertised in this phase. The API is opt-in and disabled by default.
