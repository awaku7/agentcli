# macOS MXC Seatbelt — incremental verification record

- Started: 2026-10-25 (JST).
- Work branch: `feat/macos-seatbelt-smoke`; baseline: `main` commit `5e0e6885`.
- Prior Mac baseline PR: [#276](https://github.com/awaku7/agentcli/pull/276) — **merged into main**, commit `9d7687d7` on 2026-10-25. This PR's branch was cut before the merge; keep its changes separate.
- Windows VM-grade isolation: **deferred until explicitly needed**; keep [#274](https://github.com/awaku7/agentcli/pull/274) independent.
- Support decision (2026-10-25): **Apple Silicon (ARM64) only** for this macOS Seatbelt work. Intel Mac / x86-64 is explicitly **out of scope**, not silently passing or considered supported. Already-merged PR #276 still has separate Intel basic-platform CI coverage, which this PR does not change.
- This stage is **only a non-production host verification** of the pinned Microsoft MXC SDK's macOS Seatbelt backend. It does not enable the UAG Sandbox toggle, Remote Web/A2A, or Enterprise high-isolation guarantees.

## Evidence and work log

| Date (JST) | Activity | Evidence / status | Next action |
| --- | --- | --- | --- |
| 2026-10-25 | Upstream review | MXC documents the macOS Seatbelt backend for macOS 15+, a per-process-tree mechanism, with deny-all network and filesystem allow/deny support. It cannot filter arbitrary remote hosts, has no named container lifecycle, and cannot replace VM-grade security controls. | Only verify the narrow local Seatbelt behavior; do not relax fail-closed UAG host routing. |
| 2026-10-25 | Start of implementation | Created `feat/macos-seatbelt-smoke` from `main`; no Python or existing UAG execution routing changes. | Prove the pinned SDK on real macOS hosts before integrating a production adapter. |
| 2026-10-25 | Real-host verification code | Commit `eb02cf53` adds `seatbelt_smoke.mjs`: workspace file read/write, denied host-only canary, and host-loopback denial while an actual host listener is reachable. | Execute with pinned SDK on ARM64/Intel GitHub macOS runners. |
| 2026-10-25 | CI matrix | Commit `2c4a0e39` adds an independent macOS 15 Apple Silicon + Intel workflow. SDK installed with pinned lockfile; JavaScript syntax checked before real execution. | Inspect CI errors and fix only well-understood failures. |
| 2026-10-25 | First real macOS test failure | Run [`40180533181`](https://github.com/awaku7/agentcli/actions/runs/40180533181): ARM64 allowed workspace writes and denied canary reads, but the host test TCP listener emitted an unhandled `ECONNRESET` when the host probe deliberately disconnected. This was a **test harness error**, not a successful network isolation result. | Make the disposable test listener handle socket resets, then rerun on both Macs. |
| 2026-10-25 | Test harness correction | Commit `9efa3847` handles the disposable listener's reset event. | Recheck real host results; do not change UAG sandbox policy. |
| 2026-10-25 | ARM64 verified | In run [`40180599384`](https://github.com/awaku7/agentcli/actions/runs/40180599384), macOS 15 ARM64 **passed** the real Seatbelt SDK smoke: workspace read/write, host canary read denied, and live host-loopback listener denied. | Intel must pass independently before a two-architecture claim. |
| 2026-10-25 | Intel native binary blocker | Same run, macOS 15 Intel **failed** before executing a Seatbelt subprocess: pinned `@microsoft/mxc-sdk@1.0.0` searched for `bin/x64/libmxc_ffi.dylib` and alternate x86_64-apple-darwin paths; none were present. This is a missing runtime binary in the installed pinned package, not evidence of a Seatbelt policy defect. | Investigate separately whether a trusted official x64 artifact exists, and validate any SDK bump in a dedicated review; **do not** copy binaries from the ARM64 package or relax the fail-closed gate. |
| 2026-10-25 | Codex review P2 | [Finding](https://github.com/awaku7/agentcli/pull/277#discussion_r4370354642): denied canary and network probes accepted nonzero or null exit codes even when MXC timed out, making test success a false positive. | Assert normal terminal result and actual command execution, not just nonzero status. |
| 2026-10-25 | Tighten negative probes | Commit `c75f55fd` rejects timed-out and non-integer-exit probes; requires both denied tests to emit a shell-start sentinel; requires canary stderr to report access denied, and proves `nc` reaches the same test listener outside the sandbox before asserting its sandbox failure. Passed macOS ARM64 in run `40183351203`. | Verify macOS ARM64 still passes the stricter negative checks; Intel SDK native FFI is separately blocked. |
| 2026-10-25 | Stricter ARM64 verification | [Run `40183351203`](https://github.com/awaku7/agentcli/actions/runs/40183351203) passed the `macos-15` ARM64 Seatbelt job **with** normal-exit assertions, the shell-start sentinels, filesystem denial stderr, and a host-side `nc` positive control. | Ask Codex to independently re-review the P2 fix before resolving the thread. |
| 2026-10-25 | Intel blocker reproduced | Same run `40183351203`: `macos-15-intel` failed again at MXC FFI load because `@microsoft/mxc-sdk@1.0.0` contains no discoverable Intel `libmxc_ffi.dylib` at expected paths. Real Seatbelt behavior remains **unverified** on Intel. | Leave the Intel job red and PR Draft until trusted official x64 runtime dependency is available; do not hide this in optional skips. |

| 2026-10-25 | Codex re-review P2 | [Review finding](https://github.com/awaku7/agentcli/pull/277#discussion_r4370457627) on `87da3286`: network probe still accepted any ordinary nonzero exit even if `nc` could not run or the connection was refused; the host-side positive control alone did not establish permission denial inside Seatbelt. | Require the sandboxed `nc` stderr to identify a failed connect/connectx to the exact loopback listener with a permissions error. |
| 2026-10-25 | Network denial evidence strengthened | Commit `b5efe436` uses verbose `nc` on both host positive control and contained probe, and asserts a platform-standard `connect/connectx to 127.0.0.1 port <same port> ... Operation not permitted/Permission denied` failure diagnostic. This fails closed if `nc` is missing, options are invalid, the listener refuses the connection, or output is ambiguous. **Real-host acceptance pending new macOS CI**. | Check ARM64 result and fix only grounded diagnostic differences. Intel remains blocked independently by missing SDK 1.0.0 FFI. |

| 2026-10-25 | Real-host check after exact permission-denial fix | [Latest run `40184164368`](https://github.com/awaku7/agentcli/actions/runs/40184164368) on `369be001`: macOS 15 ARM64 **success** using verbose host and contained `nc`, with an explicit `connect/connectx` denial diagnostic. macOS 15 Intel **failure** due to the unchanged missing pinned MXC native `libmxc_ffi.dylib` before Seatbelt launches. Both outcomes observed in completed job results, not inferred from static code. | Reply on Codex P2 review thread, request a fresh review, and keep the PR draft with Intel unsupported. |

| 2026-10-25 | Codex independent follow-up complete | Codex review of `e890a856` **completed with no findings**, and both P2 inline threads (negative-probe timeout and network errno proof) were resolved after successful ARM64 CI. [Review summary](https://github.com/awaku7/agentcli/pull/277#issuecomment-6395994673). | Keep PR Draft and Intel Seatbelt CI red until pinned x64 FFI is available or a separate accepted scope change is agreed. Do not infer two-architecture acceptance. |

| 2026-10-25 | Scope decision: Apple Silicon only | Intel Mac support is **not required** for the current UAG macOS Seatbelt feature. Commit `2059ea3e` removes the Intel runner from the Seatbelt workflow (rather than reporting the missing native FFI as an accepted or skipped test). Commit `e9cc1a71` makes the test explicitly reject non-ARM64 hosts. Historical Intel failures remain recorded above. The already-merged baseline PR #276 stays untouched. | Require a fresh successful Apple Silicon real-host CI and a new review for this scope-only follow-up; production macOS sandbox is still not enabled. |

## Required gates before any production UAG macOS sandbox implementation

1. The **Apple Silicon/macOS ARM64** job must execute the real Seatbelt subprocess and pass all assertions; successful installation or syntax check alone is insufficient. Intel Mac is not an acceptance criterion for this PR.
2. A future production host adapter must enforce a bounded process-tree stop, maximum execution/CPU/memory and workspace usage, and verify cleanup before reusing a scope. Seatbelt does not itself provide a persistent container or cgroup-style resource lifecycle.
3. No credential, arbitrary host path, network, home-folder, or other scope leakage. Run real denied-action tests, cancellation and crash tests, and session transitions.
4. CLI/GUI/local Web should remain opt-in for Sandbox; unsupported macOS Sandbox currently remains fail-closed. Remote Web and A2A must not automatically rely on this PoC.
5. Python code changes (in a later PR) must be formatted with the repository-pinned Black and verified by `python -m black --check`, Ruff, targeted pytest, existing regression tests and macOS CI before commit. Never report unexecuted tests as passed.

## Verification ledger

- Node syntax check: **passed** on supported ARM64, run `40184164368`.
- macOS 15 ARM64 real Seatbelt: **passed with exact-denial assertion**, run `40184164368`.
- macOS 15 Intel/x86-64 real Seatbelt: **not supported by this PR by decision**, rather than counted as passed or silently skipped. Historical attempts found the missing pinned SDK 1.0.0 native `libmxc_ffi.dylib` in run `40184164368`.
- Local Mac/SDK execution: **not available**.
- Python Black/Ruff/pytest: **not applicable yet**; no Python code edited in this PoC.
- Strong isolation: **deferred**, not claimed.
