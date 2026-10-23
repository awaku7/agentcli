# PR 4 Windows Sandbox acceptance gate

## Current disposition

PR 4 is **not accepted** and Remote execution must remain fail-closed. The Windows MXC local `ProcessContainer` backend is not a VM backend and must not be treated as one. No `windows_sandbox` production manager is wired into the Remote dispatcher.

The pinned local runtime contains `@microsoft/mxc-sdk@1.0.0` and `bin/x64/wxc-exec.exe`. Its observed CLI contract (`wxc-exec.exe --help`) includes `--experimental`, `--dry-run`, and a positional config path. A no-execution dry-run accepted the minimal `version: 1.1.0-alpha`, `containment: windows_sandbox`, and `process.commandLine` request syntax with a dedicated workspace. This environment reports Windows 11 Pro (`EditionID=Professional`, build 26200). An initial non-elevated feature query returned DISM error 740; the subsequent `-RunVmTests` invocation passed the elevation guard but reported `Containers-DisposableClientVM` disabled and stopped before launching a VM. A fuller request including `network`/`ui` fields returned `validation failed`; the cause was not isolated. None of these results proves VM isolation or backend availability.

### Latest local smoke result (2026-10-22)

After enabling Windows Sandbox and rebooting, a real one-shot run on this Windows 11 Pro host (build 26200, pinned `@microsoft/mxc-sdk@1.0.0`) completed with guest exit code 0 and emitted both `UAG_PR4_VM_SMOKE` and `UAG_PR4_HOST_PATH_BLOCKED`. The execution request explicitly set `fallback.allowDaclMutation` to `false`. Diagnostics: `%LOCALAPPDATA%\uagent\pr4_acceptance\wxc-exec-20261022-211100-528d83aed1ba413db39987f11a03b7a8.log`.

The first revised harness incorrectly waited for `vmmemWindowsSandbox` and reported a 900-second shutdown timeout. The pinned-version MXC Windows Sandbox reference says SYSTEM-owned `vmmem*` residuals are not ownership targets and do not block a new launch once `WindowsSandbox*` host processes exit. At timeout, only `vmmemWindowsSandbox` was reported; the run's temporary workspace was later removed after confirming no Windows Sandbox process remained. This timeout alone is therefore **not evidence of a live owned VM or a failed teardown**. The harness now checks/waits for `WindowsSandbox*` host processes only; it does not terminate or reclaim `vmmem*` processes.

This is smoke-test evidence only. The required network, lifecycle/resource, credentials, scope isolation, export, Browser/Computer Use, and authenticated-entrypoint matrix remains pending; PR 4 is not accepted and Remote routing remains fail-closed.

### State-aware lifecycle smoke attempt (2026-10-23)

On the same Pro host/build and pinned SDK, the first lifecycle attempt passed preflight and provisioned an owner ID, but `start` failed with executor exit code 1; the operator reported a GUI `E_ACCESSDENIED`. Owner-bound deprovision succeeded and the workspace was removed, but that helper version discarded the underlying daemon log.

A second run with the improved diagnostics again failed during `start`. Its JSON report (`%LOCALAPPDATA%\uagent\pr4_acceptance\lifecycle-20261023-142550-f81cfb1a0373474ebc09bc06443edfb3.json`) records that the daemon timed out after 360 seconds waiting for the guest rendezvous file. The daemon log says it tore down its VM, confirmed all sandbox host processes gone, cleared its record, and exited. The executor's owner-bound `deprovision` also succeeded; the helper removed its workspace. A follow-up check found no Windows Sandbox, MXC executor, or lifecycle daemon process. The GUI's `E_ACCESSDENIED` text is not present in the daemon log, so its relation to the rendezvous timeout and the underlying cause remain unconfirmed. The shared rendezvous `bootstrap.log` retained its earlier 12:26 timestamp and was not refreshed by the 14:25 run, consistent with the guest never reaching its bootstrap step. This is a failed VM lifecycle smoke, not PR4 acceptance; do not repeat it until the startup failure is diagnosed.

The first-stage schema used for the explicit smoke procedure is:

```json
{
  "version": "1.1.0-alpha",
  "containment": "windows_sandbox",
  "process": {
    "commandLine": "powershell.exe -NoLogo -NoProfile -NonInteractive -Command Write-Output UAG_PR4_VM_SMOKE",
    "timeout": 30000
  },
  "filesystem": {
    "readwritePaths": ["<one dedicated disposable scope workspace>"],
    "readonlyPaths": []
  }
}
```

The executor must be invoked with `--experimental`. Never use the V1 SDK `spawn` / `processcontainer` path as a substitute. Do not add network allow rules, proxy access, host credentials, or host-wide mounts. Do not interpret a successful dry-run as proof that Windows Sandbox was selected or started.

## Running the prepared smoke procedure

Run only from an elevated PowerShell on a dedicated Windows 11 Pro/Enterprise acceptance machine with Windows Sandbox enabled, at least 2 GB free memory, no active Windows Sandbox process in that logon session, and the exact pinned MXC runtime installed. The script checks these prerequisites and refuses before creating a test workspace if elevation, memory, or exclusivity is missing. It does not kill or reclaim unrelated Sandbox processes. It creates and removes only its unique temporary test directory.

```powershell
pwsh -File .\docs\plans\PR4_WINDOWS_SANDBOX_ACCEPTANCE.ps1
pwsh -File .\docs\plans\PR4_WINDOWS_SANDBOX_ACCEPTANCE.ps1 -RunVmTests
```

Without `-RunVmTests`, the script performs CLI/schema preflight only and never launches a VM. `-RunVmTests` performs the positive smoke and host-only canary denial checks within a single one-shot VM invocation, respecting MXC's one-VM-per-logon-session limit. Do not run concurrent test invocations. The script writes a unique persistent executor diagnostic log under `%LOCALAPPDATA%\uagent\pr4_acceptance\`; retain that log and verify that the actual backend is Windows Sandbox. A command marker or a passing mock is not sufficient. If temporary-workspace cleanup fails, the script reports the retained workspace and log paths and exits as incomplete; do not rerun until the orphaned VM/lock is resolved.

For the state-aware lifecycle smoke (provision → start → guest exec with a host-only canary → stop → deprovision), run the dedicated helper from an elevated PowerShell at the repository root:

```powershell
$env:PYTHONPATH = "src;$env:PYTHONPATH"
python scripts/run_pr4_windows_sandbox_lifecycle_smoke.py
```

It refuses to start if the host is not elevated, supported, has less than 2 GB free memory, the Sandbox feature is not enabled, or another `WindowsSandbox*` host process is present. It uses the owner-bound ID for cleanup, never force-reclaims, and preserves its workspace if provisioning has an ambiguous result or teardown cannot be confirmed. The report is written under `%LOCALAPPDATA%\uagent\pr4_acceptance\`. This smoke exercises lifecycle plumbing only; it does not test resource limits, network policy, credentials, scope separation, or qualify the backend for Remote execution.

The script is a harness starter, not a PR 4 pass. Its output must not be used to enable Remote tool routing by itself.

## Required real-VM evidence matrix

Every row must be run from the actual pinned `wxc-exec.exe` Windows Sandbox VM on the supported Pro host, using the current code and the same isolation profile intended for production. Record executor/runtime versions, OS edition/build, test command, expected and actual results, cleanup outcome, and diagnostic artifact path. Mock, declared capability, and dry-run results are not evidence.

| Area | Required negative/positive exercise | Status |
| --- | --- | --- |
| Backend selection | Pro host launches a real `windows_sandbox` VM; unsupported editions/features reject without fallback to ProcessContainer or Host. | Pending |
| Scope/workspace | Dedicated workspace only; two principals/rooms/tasks/projects cannot enumerate or read each other's files. Host Home, credential stores, management sockets, repository, and unshared temp paths remain unavailable. | Pending |
| Network | Egress is block-only. Test public IP, DNS, metadata/private/link-local destinations, host management/listener ports, and direct proxy bypass. Never grant proxy/egress allow as a workaround. | Pending |
| Child processes/lifecycle | Spawn a child, cancel/timeout/crash/stop the operation, and verify the VM and every child are gone before a new operation is admitted. Unknown-owner VM must not be reclaimed. | Pending |
| Credentials | Success, failure, cancellation, and timeout paths; no secret in environment, mounted workspace, stdout/stderr, Tool Result, telemetry, or subsequent operation. Any unavoidable secret-bearing lease is tainted and destroyed after the active Tool ends. | Pending |
| Resource limits | Test CPU, memory, process/fork count, disk/temp usage, wall time, stdout/stderr/Tool Result bytes, parallel tools/leases, and connection count where configured. Exceed each bound with real tools/children and verify bounded termination without exhausting the host or another scope. | Pending |
| Copy-out/export | Validate traversal, reparse points/symlinks, hardlinks, and concurrent revision conflicts. Reject overwrite on conflict; only an explicit approved export may modify the host project. | Pending |
| Browser/Computer Use | Browser profile, downloads, clipboard, and desktop state stay inside an isolated VM. Verify no access to Host desktop/profile/clipboard/microphone/camera/printer/shared folders. If the isolated GUI cannot be proven, Remote Computer Use remains denied with no Host fallback. | Pending |
| Entrypoints | Test authenticated Web and A2A using a real provider and representative function calls; revoke authorization during execution; verify backend absence/low capability always denies before loading or invoking a Host runner. | Pending |

## Enablement rule

Remote routing remains unavailable until every required row is supported by actual evidence and a reviewed backend integration explicitly carries that host-specific acceptance result. The current ProcessContainer probe reports only local container capabilities; it does not set Remote acceptance. Windows Home, untested Pro hosts, other operating systems, and any incomplete capability profile must continue to deny Remote tools. Enterprise E0 and multi-instance ownership/fencing are not complete in PR 4.
