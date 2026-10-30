# UAG process auto-registration for local UAG Admin

UAG now writes a minimal, private record under the regular UAG state
directory (default `~/.uag/process_registry`) while an entrypoint is running.

Supported entrypoints: `uag` (interactive CLI), `uagg`, `uagw`, `uaga`.
No extra command, PID lookup, or token is needed. `uag admin export` and
`uag session` do not register as running agents.

Each JSON contains only `version`, `instance_id`, `entrypoint`, `pid`
and `create_time`. It contains no command, environment, path, user ID,
secret, conversation or task body. A normal exit removes the record.
A crash may leave a stale record; consumers must compare the OS process birth
time before claiming it is running, and may never use this file as
authorization for process control.

The registry is best-effort and must never prevent normal UAG startup.
On non-Windows systems it uses private directory permissions. No endpoint
is exposed to the network. A locally untrusted process running as the same OS
user can edit files, so this is **not an authorization boundary**.

For custom UAG state directories, Admin must be configured to read the same
user-state directory; it must not guess the identity of unrelated processes.
The companion Admin feature is implemented separately. The remote-host
Supervisor and any start/stop operations are outside this PR.
