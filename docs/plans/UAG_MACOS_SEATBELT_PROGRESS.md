# macOS MXC Seatbelt — incremental verification record

- Started: 2026-10-25 (JST).
- Work branch: `feat/macos-seatbelt-smoke`; baseline: `main` commit `5e0e6885`.
- Prior Mac baseline PR: [#276](https://github.com/awaku7/agentcli/pull/276) — still independent and not merged into this branch.
- Windows VM-grade isolation: **deferred until explicitly needed**; keep [#274](https://github.com/awaku7/agentcli/pull/274) independent.
- This stage is **only a non-production host verification** of the pinned Microsoft MXC SDK's macOS Seatbelt backend. It does not enable the UAG Sandbox toggle, Remote Web/A2A, or Enterprise high-isolation guarantees.

## Evidence and work log

| Date (JST) | Activity | Evidence / status | Next action |
| --- | --- | --- | --- |
| 2026-10-25 | Upstream review | MXC documents the macOS Seatbelt backend for macOS 15+, a per-process-tree mechanism, with deny-all network and filesystem allow/deny support. It cannot filter arbitrary remote hosts, has no named container lifecycle, and cannot replace VM-grade security controls. | Only verify the narrow local Seatbelt behavior; do not relax fail-closed UAG host routing. |
| 2026-10-25 | Start of implementation | Created `feat/macos-seatbelt-smoke` from `main`; no Python or existing UAG execution routing changes. | Prove the pinned SDK on real macOS hosts before integrating a production adapter. |
| 2026-10-25 | Real-host verification code | Commit `eb02cf53` adds `seatbelt_smoke.mjs`: workspace file read/write, denied host-only canary, and host-loopback denial while an actual host listener is reachable. | Execute with pinned SDK on ARM64/Intel GitHub macOS runners. |
| 2026-10-25 | CI matrix | Commit `2c4a0e39` adds an independent macOS 15 Apple Silicon + Intel workflow. SDK installed with pinned lockfile; JavaScript syntax checked before real execution. | Inspect CI errors and fix only well-understood failures. |

## Required gates before any production UAG macOS sandbox implementation

1. Both architecture jobs must execute the real Seatbelt subprocess and pass all assertions; successful installation or syntax check alone is insufficient.
2. A future production host adapter must enforce a bounded process-tree stop, maximum execution/CPU/memory and workspace usage, and verify cleanup before reusing a scope. Seatbelt does not itself provide a persistent container or cgroup-style resource lifecycle.
3. No credential, arbitrary host path, network, home-folder, or other scope leakage. Run real denied-action tests, cancellation and crash tests, and session transitions.
4. CLI/GUI/local Web should remain opt-in for Sandbox; unsupported macOS Sandbox currently remains fail-closed. Remote Web and A2A must not automatically rely on this PoC.
5. Python code changes (in a later PR) must be formatted with the repository-pinned Black and verified by `python -m black --check`, Ruff, targeted pytest, existing regression tests and macOS CI before commit. Never report unexecuted tests as passed.

## Verification ledger

- Node syntax check: **pending GitHub CI**.
- macOS 15 ARM64 real Seatbelt: **pending GitHub CI**.
- macOS 15 x86-64 real Seatbelt: **pending GitHub CI**.
- Local Mac/SDK execution: **not available**.
- Python Black/Ruff/pytest: **not applicable yet**; no Python code edited in this PoC.
- Strong isolation: **deferred**, not claimed.
