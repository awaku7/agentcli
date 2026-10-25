// Real-host macOS MXC Seatbelt smoke checks, intentionally not wired to UAG tools.
// A successful result proves these narrow SDK behaviors only (not remote isolation).
import assert from "node:assert/strict";
import { spawn } from "@microsoft/mxc-sdk/v1";
import { getPlatformSupport } from "@microsoft/mxc-sdk/v1";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import net from "node:net";
import { spawnSync } from "node:child_process";

const TIMEOUT_MS = 10_000;
const MAX_OUTPUT_BYTES = 64 * 1024;

function shellQuote(value) {
  return "'" + String(value).replaceAll("'", "'\\''") + "'";
}

async function runContained(command, workspace, deniedPaths = []) {
  const request = {
    command,
    workingDirectory: workspace,
    containment: { type: "seatbelt" },
    timeoutMs: TIMEOUT_MS,
    filesystem: {
      readwritePaths: [workspace],
      readonlyPaths: [],
      deniedPaths,
    },
    network: {
      egress: { default: "deny" },
      ingress: { default: "deny", hostLoopback: "deny" },
    },
    ui: { disable: true },
    inheritDefaultEnvironment: false,
    environment: {
      HOME: workspace,
      TMPDIR: workspace,
      PATH: "/usr/bin:/bin",
      LANG: "C",
    },
  };
  const handle = await spawn(request);
  let stdout = "";
  let stderr = "";
  const append = (current, chunk) => {
    const next = current + String(chunk);
    if (Buffer.byteLength(next, "utf8") > MAX_OUTPUT_BYTES) {
      try { handle.kill(); } catch {}
      throw new Error("MXC Seatbelt smoke output exceeded the limit");
    }
    return next;
  };
  try {
    assert.ok(handle.standardOutput && handle.standardError && handle.standardInput);
    handle.standardOutput.setEncoding("utf8");
    handle.standardError.setEncoding("utf8");
    handle.standardOutput.on("data", (chunk) => { stdout = append(stdout, chunk); });
    handle.standardError.on("data", (chunk) => { stderr = append(stderr, chunk); });
    handle.standardInput.end();
    const result = await handle.wait();
    return { result, stdout, stderr };
  } finally {
    try { handle.kill(); } catch {}
    try { handle.dispose(); } catch {}
  }
}

function assertNormallyExited(probe, description) {
  assert.ok(probe && probe.result, description + ": MXC returned no terminal result");
  assert.notEqual(probe.result.timedOut, true, description + ": process timed out");
  assert.ok(
    Number.isInteger(probe.result.exitCode) && probe.result.exitCode >= 0,
    description + ": process did not complete with a normal exit code",
  );
}

async function localServer() {
  const server = net.createServer((socket) => {
    // The host reachability probe intentionally disconnects immediately.
    // A reset on this disposable test connection is not a Seatbelt failure.
    socket.on("error", () => {});
    socket.end("host-listener");
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return server;
}

async function reachableFromHost(port) {
  await new Promise((resolve, reject) => {
    const socket = net.connect({ host: "127.0.0.1", port });
    socket.once("connect", () => { socket.destroy(); resolve(); });
    socket.once("error", reject);
    socket.setTimeout(2000, () => {
      socket.destroy();
      reject(new Error("host listener timed out"));
    });
  });
}

async function main() {
  assert.equal(process.platform, "darwin", "macOS is required");
  assert.ok(["arm64", "x64"].includes(process.arch), "64-bit macOS is required");
  const support = getPlatformSupport();
  assert.equal(support.isSupported, true, "MXC must support this host");
  assert.ok(support.availableMethods?.includes("seatbelt"), "MXC Seatbelt is unavailable");

  const root = fs.mkdtempSync(path.join(os.tmpdir(), "uag-mxc-seatbelt-"));
  const workspace = path.join(root, "workspace");
  const canary = path.join(root, "host-only-canary");
  fs.mkdirSync(workspace, { mode: 0o700 });
  const secret = "uag-test-secret-" + Date.now().toString(36);
  fs.writeFileSync(canary, secret, { mode: 0o600 });
  let server;
  try {
    const allowed = await runContained(
      "/bin/sh -c " + shellQuote("printf seatbelt-ok > ./output.txt && cat ./output.txt"),
      workspace,
      [canary],
    );
    assertNormallyExited(allowed, "workspace read/write");
    assert.equal(allowed.result.exitCode, 0, "workspace write/read must succeed");
    assert.equal(allowed.stdout.trim(), "seatbelt-ok");
    assert.equal(fs.readFileSync(path.join(workspace, "output.txt"), "utf8"), "seatbelt-ok");
    console.log("PASS: scoped workspace file read/write");

    const denied = await runContained(
      "/bin/sh -c " + shellQuote("printf canary-probe-start; /bin/cat " + shellQuote(canary)),
      workspace,
      [canary],
    );
    assertNormallyExited(denied, "denied host canary");
    assert.notEqual(denied.result.exitCode, 0, "host-only canary must be inaccessible");
    assert.ok(denied.stdout.includes("canary-probe-start"), "canary probe did not start");
    assert.ok(!denied.stdout.includes(secret), "canary content leaked");
    assert.match(
      denied.stderr,
      /operation not permitted|permission denied/i,
      "canary probe did not report a filesystem access denial",
    );
    console.log("PASS: host-only canary read denied");

    server = await localServer();
    const address = server.address();
    assert.ok(address && typeof address !== "string");
    await reachableFromHost(address.port);
    // The exact nc binary/arguments must work without the sandbox, so missing
    // tools and invalid flags cannot masquerade as a denied connection.
    const hostNc = spawnSync(
      "/usr/bin/nc", ["-z", "-w", "2", "127.0.0.1", String(address.port)],
      { encoding: "utf8", timeout: 3000 },
    );
    assert.ifError(hostNc.error);
    assert.equal(hostNc.signal, null, "host nc was terminated");
    assert.equal(hostNc.status, 0, "host nc must reach the listener: " + hostNc.stderr);
    const networking = await runContained(
      "/bin/sh -c " + shellQuote("printf network-probe-start; /usr/bin/nc -z -w 2 127.0.0.1 " + address.port),
      workspace,
      [canary],
    );
    assertNormallyExited(networking, "denied host loopback");
    assert.ok(networking.stdout.includes("network-probe-start"), "network probe did not start");
    assert.notEqual(networking.result.exitCode, 0, "sandbox must deny host loopback");
    console.log("PASS: loopback connection denied with reachable host listener");
    console.log("MXC macOS Seatbelt host smoke passed for " + process.arch);
  } finally {
    if (server) await new Promise((resolve) => server.close(resolve));
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error("MXC Seatbelt host smoke FAILED:", error);
  process.exitCode = 1;
});
