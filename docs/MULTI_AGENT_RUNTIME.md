# Multi-Agent and Remote Runtime

## Local orchestration

`uagent.runtime.multi_agent.run_agents()` runs independent agent tasks concurrently and returns results keyed by stable agent names.

```python
result = await run_agents([
    AgentTask("research", research_agent),
    AgentTask("review", review_agent),
])
```

Set `fail_fast=False` to collect exceptions as result values for reporting. Duplicate agent names are rejected.

## Remote A2A runtime

`RemoteAgentRuntime` wraps the A2A client for a remote agent endpoint:

```python
runtime = RemoteAgentRuntime(base_url="https://agent.example.com", token=token)
try:
    task = runtime.submit("summarize this", return_immediately=True)
finally:
    runtime.close()
```

Authentication uses the shared CredentialStore when supplied. Stable protocol values and error codes are not localized; user-facing clients should translate only their presentation.

Remote execution remains subject to A2A authentication, ToolPolicy, Enterprise Policy, cancellation, and task-store behavior on the remote server.
