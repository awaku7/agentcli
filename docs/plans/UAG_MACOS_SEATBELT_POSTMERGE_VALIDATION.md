# UAG macOS ARM64 Seatbelt — post-merge acceptance

Date: 2026-10-25  
Baseline: PR #278 merged to `main` as `99b6376a`  
Purpose: verify user-facing tool isolation after integration **without narrowing CLI, GUI, Web, Remote Web or A2A features**. Intel Mac is not an MXC Seatbelt target. VM-grade/strong isolation remains deferred.

## Automated real-host acceptance

Run `macOS MXC Seatbelt smoke` on an **Apple Silicon macOS 15** GitHub Actions runner. The opt-in `tests/test_mxc_macos_integration.py` now covers:

1. Normal file creation/reading and confined `python_exec` from CLI, GUI, Web Room and A2A scopes.
2. Host-only file read and loopback access denial with host-side positive control.
3. Child process reaping for an ordinary child and a detached `setsid` child; host PID survival is checked explicitly.
4. **New post-merge tests**: absolute and traversal-path denial in file tools; allowlist denial of `cmd_exec`; symlink escape denial; Python write denial against an existing host canary; two different entry-point scopes cannot share or read each other's workspace; Remote VM-required routing cannot silently downgrade to Seatbelt.

Do not report a negative test as passed simply because the operation failed for an unrelated setup, parse, missing-binary or timeout reason. Preserve post-test canary state and exact response assertions. On test failure, leave the PR unmerged, inspect Apple Silicon runner logs, fix the issue, and request an independent review.

The CI host is a **real Apple Silicon GitHub runner**, but it is not the maintainer's personal Mac. CI cannot prove every locally installed toolchain, GUI interaction, provider, or Remote deployment configuration.

## Hands-on Apple Silicon checklist

Prerequisites: Apple Silicon ARM64, supported macOS version, trusted Node.js 24.21+ ARM64 (or supported 26.x), npm, and an installed UAG Python environment.

- Confirm host and Python: `uname -m`, `sw_vers`, `python --version`, `node --version`.
- Launch CLI with explicit `uag --sandbox mxc`. Verify first-run setup/approval, then use only a disposable project workspace. Confirm create/read operations succeed and that requests for paths outside the sandbox are denied.
- Launch Desktop with `uagg --sandbox mxc`. Repeat the same benign and denied tools. Confirm the desktop can restart without retaining an unverified active worker.
- In Web Room, explicitly enable the same MXC sandbox. Verify each room/user has an independent workspace; closing and re-opening a room must honor its binding generation and lease.
- In Remote Web and tool-enabled A2A, use their existing sandbox activation/authorization configuration. Confirm tools work only for an authenticated, correctly bound scope; an unregistered tool and a stale/revoked scope remain denied. Do **not** create a publicly exposed Remote endpoint just to perform this check.
- Request a VM-level minimum explicitly (where applicable). It must **fail closed** until a genuinely accepted VM-grade backend exists; macOS Seatbelt must not be represented as one.
- Terminate an active session and verify that tracked child processes stop. Do not test with production data, real credentials, or destructive host paths.

Record host architecture, macOS release, UAG/Node/Python versions, the mode used, observed results, and the exact CI run. Never publish credentials or private workspace paths.

## Security acceptance boundary

MXC Seatbelt is an operating-system enforced lightweight subprocess boundary. The macOS host resource supervisor uses sampled process accounting rather than hard cgroup/Job Object limits; it is **not** a production multi-tenant, VM-grade or Enterprise E0 guarantee. Higher required isolation tiers must fail closed. Never broaden tool permissions to make a test pass.
