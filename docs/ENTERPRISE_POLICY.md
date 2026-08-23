# Enterprise Policy Engine

uag can apply organization-level rules to tools, providers, credentials, MCP servers, networks, skills, and plugins.

## Unified policy model

The public policy entry point is `UnifiedPolicy`. It combines the process permission level, the existing side-effect policy, and the enterprise YAML rules. Operators normally need to configure only `UAGENT_POLICY_FILE`; `UAGENT_POLICY_LEVEL` is an optional development-time restriction.

```text
UAGENT_POLICY_LEVEL=read_only
```

Available levels are `none`, `read_only`, `propose_only`, `write`, and `admin`. A stricter runtime permission cannot be relaxed by YAML. Enterprise `deny` rules always win, while `confirm` rules require the normal confirmation callback.

## Enable a policy

Set `UAGENT_POLICY_FILE` to a JSON or YAML policy file:

```text
UAGENT_POLICY_FILE=/path/to/uagent-policy.yaml
```

The file is loaded at startup. If it does not exist, uag creates an empty `{}` policy file, which means allow-all and preserves the existing behavior. When the file changes, uag reloads it automatically before the next policy evaluation.

## Example

```yaml
tools:
  shell:
    action: deny
  delete_file:
    action: confirm

providers:
  openai:
    action: allow

credentials:
  provider/openai:
    action: deny

mcp_servers:
  https://trusted.example.com:
    action: allow
  https://untrusted.example.com:
    action: deny

network:
  default: deny
  allowlist:
    - trusted.example.com

skills:
  unsafe-skill:
    action: deny

plugins:
  untrusted-plugin:
    action: deny

roles:
  viewer:
    tools:
      delete_file:
        action: deny
```

Supported actions are:

- `allow`: permit the operation
- `deny`: reject the operation
- `confirm`: require the normal user confirmation flow

## Roles

Set `UAGENT_ROLE` to apply a role-specific Tool policy. A role override takes precedence over the global Tool rule.

```text
UAGENT_ROLE=viewer
```

The policy engine records structured events such as `policy.denied` and `policy.confirmation_required`. Secret values are never included in these events.

## Scope and limitations

The policy is enforced at Tool dispatch, Credential resolution, MCP connection, and plugin startup boundaries. Unknown policy actions are rejected. Network and MCP allowlists use scheme, hostname-boundary, port, and path-boundary matching; MCP configurations containing allow actions deny unregistered endpoints.

See also:

- [Improvement priority](IMPROVEMENT_PRIORITY.md)
- [Architecture](ARCHITECTURE.md)
