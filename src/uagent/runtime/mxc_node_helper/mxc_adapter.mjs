import crypto from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";

const MAX_FRAME_BYTES = 1_100_000;
const HARD_EXECUTION_TIMEOUT_MS = 60_000;
const MAX_SESSION_MS = 12 * 60 * 60 * 1000;
const MAX_WORKSPACE_BYTES = 256 * 1024 * 1024;
const MAX_WORKSPACE_ENTRIES = 5_000;
const PYTHON_OUTPUT_LIMIT = 64 * 1024;
const execFileAsync = promisify(execFile);

function writeHost(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function quoteWindowsArgument(value) {
  const text = String(value);
  return `"${text.replace(/(\\*)"/g, "$1$1\\\"").replace(/(\\+)$/g, "$1$1")}"`;
}

function quotePosixArgument(value) {
  const quote = String.fromCharCode(39);
  const slash = String.fromCharCode(92);
  return quote + String(value).split(quote).join(quote + slash + quote + quote) + quote;
}

function quoteArgument(value) {
  return process.platform === "win32"
    ? quoteWindowsArgument(value)
    : quotePosixArgument(value);
}

function readHostConfig() {
  return new Promise((resolve, reject) => {
    let text = "";
    const onData = (chunk) => {
      text += chunk.toString("utf8");
      if (Buffer.byteLength(text, "utf8") > MAX_FRAME_BYTES) {
        process.stdin.off("data", onData);
        reject(new Error("host configuration frame is too large"));
        return;
      }
      const newline = text.indexOf("\n");
      if (newline >= 0) {
        process.stdin.off("data", onData);
        try {
          resolve(JSON.parse(text.slice(0, newline)));
        } catch (error) {
          reject(error);
        }
      }
    };
    process.stdin.on("data", onData);
    process.stdin.once("error", reject);
    process.stdin.resume();
  });
}

async function probeHost() {
  const handshake = await readHostConfig();
  if (!handshake || handshake.probe !== true) {
    throw new Error("MXC probe requires the bounded host-adapter handshake");
  }
  if (process.platform === "darwin" && process.arch === "arm64") {
    const { getPlatformSupport, getAvailableBackends } = await import("@microsoft/mxc-sdk/v1");
    const support = getPlatformSupport();
    const backends = getAvailableBackends();
    if (!support.isSupported || !support.availableMethods?.includes("seatbelt")) {
      throw new Error("MXC SDK does not report macOS ARM64 Seatbelt support");
    }
    // The verified SDK smoke performs real positive and negative filesystem,
    // network and subprocess checks. Never accept metadata-only support.
    const helper = path.join(import.meta.dirname, "seatbelt_smoke.mjs");
    const evidence = await execFileAsync(process.execPath, [helper], {
      cwd: import.meta.dirname,
      env: {
        PATH: "/usr/bin:/bin",
        HOME: process.env.HOME,
        TMPDIR: process.env.TMPDIR || "/tmp",
        LANG: "C",
      },
      timeout: 30_000,
      maxBuffer: 32 * 1024,
    });
    const passed = evidence.stdout.includes("MXC macOS Seatbelt host smoke passed for arm64");
    if (!passed) throw new Error("macOS Seatbelt host smoke did not prove the required isolation");
    writeHost({
      ok: true,
      sdk: "@microsoft/mxc-sdk@1.0.0",
      node: process.versions.node,
      platform: process.platform,
      arch: process.arch,
      backend: "seatbelt",
      support,
      backends,
      proof: "filesystem-deny,workspace-readwrite,loopback-connect-permission-denied",
    });
    return;
  }
  if (process.platform === "linux" && process.arch === "x64") {
    const { getAvailableBackends, getPlatformSupport, spawn } = await import("@microsoft/mxc-sdk/v1");
    const support = getPlatformSupport();
    const backends = getAvailableBackends();
    if (!support.isSupported || !support.availableMethods?.includes("bubblewrap")) {
      writeHost({ ok: false, error: "MXC SDK does not report Linux Bubblewrap support", support, backends });
      process.exitCode = 2;
      return;
    }
    const request = {
      command: "/usr/bin/true",
      workingDirectory: "/",
      containment: { type: "process" },
      timeoutMs: 10_000,
      filesystem: { readwritePaths: [], readonlyPaths: ["/usr", "/lib", "/lib64"], deniedPaths: [] },
      network: { egress: { default: "deny" }, ingress: { default: "deny", hostLoopback: "deny" } },
      ui: { disable: true },
      inheritDefaultEnvironment: false,
      environment: { HOME: "/tmp", PATH: "/usr/bin:/bin", LANG: "C.UTF-8" },
    };
    let processHandle;
    let terminal;
    let stderrText = "";
    try {
      processHandle = await spawn(request);
      const stderrStream = processHandle.standardError;
      if (stderrStream) {
        stderrStream.setEncoding("utf8");
        stderrStream.on("data", (chunk) => {
          stderrText = (stderrText + chunk).slice(-4096);
        });
      }
      terminal = await processHandle.wait();
    } finally {
      try { processHandle?.dispose(); } catch {}
    }
    const accepted = terminal?.exitCode === 0 && terminal?.timedOut !== true;
    writeHost({
      ok: accepted,
      sdk: "@microsoft/mxc-sdk@1.0.0",
      node: process.versions.node,
      platform: process.platform,
      arch: process.arch,
      backend: "bubblewrap",
      support,
      backends,
      probe: {
        exitCode: terminal?.exitCode,
        timedOut: terminal?.timedOut === true,
        stderr: stderrText,
      },
      error: accepted ? undefined : "MXC Bubblewrap probe did not complete successfully",
    });
    if (!accepted) process.exitCode = 2;
    return;
  }
  if (process.platform !== "win32" || process.arch !== "x64") {
    writeHost({ ok: false, error: "MXC supports Windows/Linux x64 or macOS ARM64 in this release" });
    process.exitCode = 2;
    return;
  }
  const { getAvailableBackends, getPlatformSupport, probe } = await import("@microsoft/mxc-sdk/v1");
  const support = getPlatformSupport();
  const backends = getAvailableBackends();
  const windowsRoot = process.env.SystemRoot || path.win32.join(process.env.SystemDrive || "C:", "Windows");
  const request = {
    command: "cmd.exe /d /s /c exit 0",
    containment: { type: "processcontainer" },
    fallback: { allowDaclMutation: false },
    timeoutMs: 10_000,
    filesystem: { readwritePaths: [], readonlyPaths: [path.join(windowsRoot, "System32")], deniedPaths: [] },
    network: { egress: { default: "deny" }, ingress: { default: "deny", hostLoopback: "deny" } },
    ui: { disable: true },
    inheritDefaultEnvironment: false,
    environment: { SystemRoot: windowsRoot, WINDIR: windowsRoot, PATH: path.join(windowsRoot, "System32") },
  };
  const result = probe(request);
  const accepted = Boolean(
    support.isSupported &&
    support.availableMethods?.includes("processcontainer") &&
    result.tier === "base-container" &&
    result.needsDaclAugmentation === false &&
    Array.isArray(result.warnings) && result.warnings.length === 0 &&
    result.probes?.baseContainerApiPresent === true &&
    result.probes?.baseContainerSupportsDenyPaths === true
  );
  writeHost({
    ok: accepted,
    sdk: "@microsoft/mxc-sdk@1.0.0",
    node: process.versions.node,
    platform: process.platform,
    arch: process.arch,
    support,
    backends,
    probe: result,
    error: accepted ? undefined : "MXC did not prove the required BaseContainer policy on this host",
  });
  if (!accepted) process.exitCode = 2;
}

function createReplyQueue(stdout, processHandle) {
  let buffered = "";
  const replies = [];
  const waiters = [];
  let closedError = null;
  const settle = (line) => {
    let value;
    try {
      value = JSON.parse(line);
    } catch (error) {
      closedError = new Error(`invalid sandbox worker response: ${error}`);
      processHandle.kill();
      while (waiters.length) waiters.shift().reject(closedError);
      return;
    }
    const waiter = waiters.shift();
    if (waiter) waiter.resolve(value);
    else replies.push(value);
  };
  stdout.setEncoding("utf8");
  stdout.on("data", (chunk) => {
    buffered += chunk;
    if (Buffer.byteLength(buffered, "utf8") > MAX_FRAME_BYTES) {
      closedError = new Error("sandbox worker exceeded the IPC frame limit");
      processHandle.kill();
      while (waiters.length) waiters.shift().reject(closedError);
      return;
    }
    let newline;
    while ((newline = buffered.indexOf("\n")) >= 0) {
      const line = buffered.slice(0, newline);
      buffered = buffered.slice(newline + 1);
      settle(line);
    }
  });
  stdout.on("error", (error) => {
    closedError = error;
    while (waiters.length) waiters.shift().reject(error);
  });
  stdout.on("end", () => {
    closedError ||= new Error("sandbox worker stdout closed");
    while (waiters.length) waiters.shift().reject(closedError);
  });
  return (timeoutMs) => {
    if (replies.length) return Promise.resolve(replies.shift());
    if (closedError) return Promise.reject(closedError);
    return new Promise((resolve, reject) => {
      const waiter = { resolve: null, reject: null };
      const timer = setTimeout(() => {
        const index = waiters.indexOf(waiter);
        if (index >= 0) waiters.splice(index, 1);
        reject(new Error("sandbox worker response timed out"));
      }, timeoutMs);
      waiter.resolve = (value) => { clearTimeout(timer); resolve(value); };
      waiter.reject = (error) => { clearTimeout(timer); reject(error); };
      waiters.push(waiter);
    });
  };
}

const ALTERNATE_STREAM_SCAN_SCRIPT = [
  "$ErrorActionPreference = 'Stop'",
  "$ProgressPreference = 'SilentlyContinue'",
  "$source = @'",
  "using System;",
  "using System.Runtime.InteropServices;",
  "public static class UagentMxcStreamScan {",
  "  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]",
  "  public struct Data {",
  "    public long StreamSize;",
  "    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 296)] public string StreamName;",
  "  }",
  "  [DllImport(\"kernel32.dll\", CharSet = CharSet.Unicode, SetLastError = true)]",
  "  public static extern IntPtr FindFirstStreamW(string path, int level, out Data data, uint flags);",
  "  [DllImport(\"kernel32.dll\", CharSet = CharSet.Unicode, SetLastError = true)]",
  "  public static extern bool FindNextStreamW(IntPtr handle, out Data data);",
  "  [DllImport(\"kernel32.dll\", SetLastError = true)]",
  "  public static extern bool FindClose(IntPtr handle);",
  "}",
  "'@",
  "Add-Type -TypeDefinition $source",
  "$root = $env:UAGENT_MXC_SCAN_ROOT",
  "$rootFull = [IO.Path]::GetFullPath($root).TrimEnd([char[]]@(92,47))",
  "function Test-VanishedWorkspacePathError($record) {",
  "  if ($record.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound) { return $true }",
  "  $exception = $record.Exception",
  "  while ($null -ne $exception) {",
  "    if ($exception -is [IO.FileNotFoundException] -or $exception -is [IO.DirectoryNotFoundException]) { return $true }",
  "    $exception = $exception.InnerException",
  "  }",
  "  return $false",
  "}",
  "$rootItem = Get-Item -LiteralPath $root -Force -ErrorAction Stop",
  "$items = [System.Collections.Generic.List[object]]::new()",
  "[void]$items.Add($rootItem)",
  "$pending = [System.Collections.Generic.Stack[string]]::new()",
  "if ($rootItem.PSIsContainer) { $pending.Push($rootFull) }",
  "while ($pending.Count -gt 0) {",
  "  $directoryPath = $pending.Pop()",
  "  try { $children = @(Get-ChildItem -LiteralPath $directoryPath -Force -ErrorAction Stop) } catch {",
  "    if (-not [String]::Equals($directoryPath, $rootFull, [StringComparison]::OrdinalIgnoreCase) -and (Test-VanishedWorkspacePathError $_)) { continue }",
  "    throw",
  "  }",
  "  foreach ($child in $children) {",
  "    [void]$items.Add($child)",
  "    if ($child.PSIsContainer -and ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) { $pending.Push($child.FullName) }",
  "  }",
  "}",
  "[long]$total = 0",
  "[long]$streamCount = 0",
  "foreach ($item in $items) {",
  "  if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }",
  "  $itemFullName = [IO.Path]::GetFullPath($item.FullName).TrimEnd([char[]]@(92,47))",
  "  $isRoot = [String]::Equals($itemFullName, $rootFull, [StringComparison]::OrdinalIgnoreCase)",
  "  [long]$itemTotal = 0",
  "  [long]$itemStreamCount = 0",
  "  $streamData = New-Object UagentMxcStreamScan+Data",
  "  $handle = [UagentMxcStreamScan]::FindFirstStreamW($item.FullName, 0, [ref]$streamData, 0)",
  "  if ($handle -eq [IntPtr](-1)) {",
  "    $winError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()",
  "    if ($winError -eq 38) { continue }",
  "    if (-not $isRoot -and ($winError -eq 2 -or $winError -eq 3)) { continue }",
  "    throw \"FindFirstStreamW failed: $winError\"",
  "  }",
  "  try {",
  "    do {",
  "      if ($streamData.StreamName -ne '::$DATA') {",
  "        $itemTotal += [long]$streamData.StreamSize",
  "        $itemStreamCount += 1",
  "      }",
  "      $hasNext = [UagentMxcStreamScan]::FindNextStreamW($handle, [ref]$streamData)",
  "    } while ($hasNext)",
  "    $winError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()",
  "  } finally { [void][UagentMxcStreamScan]::FindClose($handle) }",
  "  if ($winError -eq 38) {",
  "    $total += $itemTotal",
  "    $streamCount += $itemStreamCount",
  "  } elseif (-not $isRoot -and ($winError -eq 2 -or $winError -eq 3)) {",
  "    continue",
  "  } else {",
  "    throw \"FindNextStreamW failed: $winError\"",
  "  }",
  "}",
  "[Console]::Out.WriteLine(('{0},{1}' -f $total.ToString([Globalization.CultureInfo]::InvariantCulture), $streamCount.ToString([Globalization.CultureInfo]::InvariantCulture)))",
].join("\n");

async function alternateStreamUsage(root) {
  if (process.platform !== "win32") return { bytes: 0, entries: 0 };
  const systemRoot = process.env.SystemRoot || process.env.WINDIR || String.raw`C:\Windows`;
  const powershell = path.join(systemRoot, "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
  const { stdout: output } = await execFileAsync(
    powershell,
    ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", ALTERNATE_STREAM_SCAN_SCRIPT],
    {
      encoding: "utf8",
      maxBuffer: 64 * 1024,
      timeout: 5_000,
      windowsHide: true,
      env: {
        SystemRoot: systemRoot,
        WINDIR: systemRoot,
        PATH: path.join(systemRoot, "System32"),
        TEMP: process.env.TEMP || "",
        TMP: process.env.TMP || "",
        UAGENT_MXC_SCAN_ROOT: path.resolve(root),
      },
    },
  );
  const match = output.trim().match(/^(\d+),(\d+)$/);
  if (!match) throw new Error("NTFS alternate-stream scan returned invalid output");
  const bytes = Number(match[1]);
  const entries = Number(match[2]);
  if (!Number.isSafeInteger(bytes) || !Number.isSafeInteger(entries)) {
    throw new Error("NTFS alternate-stream usage is not a safe integer");
  }
  return { bytes, entries };
}

async function workspaceUsage(root) {
  let bytes = 0;
  let entries = 0;
  const rootPath = path.resolve(root);
  const foldPath = (value) => process.platform === "win32" ? value.toLowerCase() : value;
  const resolvedRoot = foldPath(rootPath);
  const rootPrefix = foldPath(`${rootPath}${path.sep}`);
  const pending = [rootPath];
  const vanishedChild = (entry, error) =>
    entry !== rootPath && error?.code === "ENOENT";

  while (pending.length) {
    const entry = pending.pop();
    let stat;
    try {
      stat = fs.lstatSync(entry);
    } catch (error) {
      if (vanishedChild(entry, error)) continue;
      throw error;
    }
    if (stat.isSymbolicLink()) continue;
    let resolved;
    try {
      resolved = foldPath(fs.realpathSync(entry));
    } catch (error) {
      if (vanishedChild(entry, error)) continue;
      throw error;
    }
    if (resolved !== resolvedRoot && !resolved.startsWith(rootPrefix)) {
      return { exceeded: true, bytes, entries };
    }
    if (stat.isDirectory()) {
      let directory;
      try {
        directory = fs.opendirSync(entry);
      } catch (error) {
        if (vanishedChild(entry, error)) continue;
        throw error;
      }
      try {
        while (true) {
          let child;
          try {
            child = directory.readSync();
          } catch (error) {
            if (vanishedChild(entry, error)) break;
            throw error;
          }
          if (child === null) break;
          entries += 1;
          if (entries > MAX_WORKSPACE_ENTRIES) return { exceeded: true, bytes, entries };
          pending.push(path.join(entry, child.name));
        }
      } finally {
        directory.closeSync();
      }
    } else if (stat.isFile()) {
      bytes += stat.size;
      if (bytes > MAX_WORKSPACE_BYTES) return { exceeded: true, bytes, entries };
    }
  }
  const alternate = await alternateStreamUsage(root);
  bytes += alternate.bytes;
  entries += alternate.entries;
  if (bytes > MAX_WORKSPACE_BYTES || entries > MAX_WORKSPACE_ENTRIES) {
    return { exceeded: true, bytes, entries };
  }
  return { exceeded: false, bytes, entries };
}

async function executePythonInContainer(config, baseRequest, args, spawnMxc) {
  const code = args?.code;
  if (typeof code !== "string" || Buffer.byteLength(code, "utf8") > 1_000_000) {
    throw new Error("Python code must be a string no larger than 1 MB");
  }
  const scriptPath = path.join(baseRequest.workingDirectory, ".uag_exec.py");
  try {
    const stat = fs.lstatSync(scriptPath);
    if (!stat.isFile() || stat.isSymbolicLink()) throw new Error("unsafe Python scratch path");
    fs.unlinkSync(scriptPath);
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  const marker = `__UAG_PY_EXEC_${crypto.randomBytes(16).toString("hex")}__`;
  // Python runs atexit handlers in LIFO order; registering before user code
  // makes this marker prove that user shutdown handlers have completed. MXC's
  // native wait confirms that the one-shot MXC process container has stopped.
  const wrapper = [
    "import atexit, sys, traceback",
    "__uag_stdout = sys.stdout",
    `__uag_source = ${JSON.stringify(code)}`,
    `__uag_marker = ${JSON.stringify(marker)}`,
    "__uag_exit = 0",
    "def __uag_emit_marker():",
    "    __uag_stdout.write(chr(10) + __uag_marker + ':' + str(__uag_exit) + chr(10))",
    "    __uag_stdout.flush()",
    // On Darwin, keep the Python root alive after the completion marker
    // long enough for the host's descendant supervisor to observe children
    // even after setsid(). This does not replace kernel process isolation.
    ...(process.platform === "darwin"
      ? ["    import time as __uag_time", "    __uag_time.sleep(1.5)"]
      : []),
    "atexit.register(__uag_emit_marker)",
    "__uag_globals = {'__name__': '__main__', '__file__': '<python_exec>'}",
    "try:",
    "    exec(compile(__uag_source, '<python_exec>', 'exec'), __uag_globals, __uag_globals)",
    "except SystemExit as __uag_exc:",
    "    __uag_exit = __uag_exc.code if isinstance(__uag_exc.code, int) else (0 if __uag_exc.code is None else 1)",
    "except BaseException:",
    "    traceback.print_exc()",
    "    __uag_exit = 1",
  ].join("\n");
  const fd = fs.openSync(scriptPath, "wx", 0o600);
  try { fs.writeFileSync(fd, wrapper, { encoding: "utf8" }); } finally { fs.closeSync(fd); }
  const stdout = [];
  const stderr = [];
  let stdoutBytes = 0;
  let stderrBytes = 0;
  let outputTruncated = false;
  let stdoutTail = "";
  let markerExitCode = null;
  let workspaceLimitExceeded = false;
  let workspaceLimitReason = "";
  let processTreeUnverified = false;
  let processTreeFailureReason = "";
  let executionIncomplete = false;
  let workspaceMonitor;
  let workspaceScanRunning = false;
  let workspaceMonitorPromise = Promise.resolve();
  let processHandle;
  try {
    const command = `${quoteArgument(config.pythonExe)} -I -X utf8 -u ${quoteArgument(scriptPath)}`;
    processHandle = await spawnMxc({ ...baseRequest, command, timeoutMs: 60_000 });
    workspaceMonitor = setInterval(() => {
      if (workspaceLimitExceeded || workspaceScanRunning) return;
      workspaceScanRunning = true;
      workspaceMonitorPromise = (async () => {
        try {
          if ((await workspaceUsage(baseRequest.workingDirectory)).exceeded) {
            workspaceLimitExceeded = true;
            workspaceLimitReason = "monitor_exceeded";
            processHandle.kill();
          }
        } catch (error) {
          workspaceLimitExceeded = true;
          workspaceLimitReason = `monitor_error:${error?.code || error?.name || "unknown"}`;
          try { processHandle.kill(); } catch {}
        } finally {
          workspaceScanRunning = false;
        }
      })();
    }, 250);
    const out = processHandle.standardOutput;
    const err = processHandle.standardError;
    const input = processHandle.standardInput;
    if (!out || !err || !input) throw new Error("MXC Python process did not provide standard pipes");
    const capture = (chunks, which) => (chunk) => {
      const data = Buffer.from(chunk);
      const used = which === "stdout" ? stdoutBytes : stderrBytes;
      const remaining = Math.max(0, PYTHON_OUTPUT_LIMIT - used);
      if (data.length > remaining) outputTruncated = true;
      if (remaining > 0) chunks.push(data.subarray(0, remaining));
      if (which === "stdout") {
        stdoutBytes += Math.min(data.length, remaining);
        stdoutTail = (stdoutTail + data.toString("utf8")).slice(-(marker.length + 32));
        const match = stdoutTail.match(new RegExp(`${marker}:(-?[0-9]+)`));
        if (match) markerExitCode = Number(match[1]);
      } else {
        stderrBytes += Math.min(data.length, remaining);
      }
    };
    out.on("data", capture(stdout, "stdout"));
    err.on("data", capture(stderr, "stderr"));
    input.end();
    const waitPromise = processHandle.wait();
    const rootExit = waitPromise.then((terminal) => ({ kind: "exit", terminal }), (error) => ({ kind: "error", error }));
    let markerPoll;
    const markerReached = new Promise((resolve) => {
      markerPoll = setInterval(() => {
        if (markerExitCode !== null) resolve({ kind: "complete" });
      }, 10);
    });
    let executionTimer;
    const timeout = new Promise((resolve) => {
      executionTimer = setTimeout(() => resolve({ kind: "timeout" }), 30_000);
    });
    const outcome = await Promise.race([rootExit, markerReached, timeout]);
    let timedOut = outcome.kind === "timeout";
    let terminal;
    let processStopped = false;
    const waitForRoot = async (timeoutMs, timeoutKind = "stop_timeout") => {
      let timer;
      const result = await Promise.race([
        rootExit,
        new Promise((resolve) => {
          timer = setTimeout(() => resolve({ kind: timeoutKind }), timeoutMs);
        }),
      ]);
      clearTimeout(timer);
      return result;
    };
    const acceptRootExit = (result) => {
      if (result.kind === "exit") {
        terminal = result.terminal;
        processStopped = true;
      } else {
        processTreeUnverified = true;
        processTreeFailureReason = result.kind === "error"
          ? "mxc_wait_failed"
          : "mxc_wait_timeout";
      }
    };
    const stopThroughMxc = async () => {
      try { processHandle.kill(); } catch {
        // MXC wait() independently runs terminate_and_reap() on its Job Object.
        // A successful wait is the cleanup confirmation; wait failures below
        // still mark the tree unverified and tear down the host session.
      }
      acceptRootExit(await waitForRoot(15_000));
    };

    if (outcome.kind === "exit" || outcome.kind === "error") {
      acceptRootExit(outcome);
    } else {
      // The marker is emitted only after user atexit handlers have completed.
      // Use MXC's native kill/wait path to stop the isolated process tree.
      if (outcome.kind === "timeout") timedOut = true;
      if (process.platform === "darwin" && outcome.kind === "complete") {
        // The completion marker is emitted while the root is still alive.
        // Let the host sampler record detached descendants with a verifiable
        // parent before killing the MXC one-shot process.
        await new Promise((resolve) => setTimeout(resolve, 600));
      }
      await stopThroughMxc();
    }
    if (processStopped && terminal?.timedOut) timedOut = true;
    if (
      processStopped &&
      markerExitCode === null &&
      !workspaceLimitExceeded &&
      !timedOut
    ) {
      let markerTimer;
      await Promise.race([
        markerReached,
        new Promise((resolve) => { markerTimer = setTimeout(resolve, 100); }),
      ]);
      clearTimeout(markerTimer);
      executionIncomplete = markerExitCode === null;
    }
    clearInterval(markerPoll);
    clearInterval(workspaceMonitor);
    clearTimeout(executionTimer);
    await workspaceMonitorPromise;
    // The interval is only a watchdog; it may not fire if Python exits quickly.
    // Recheck after the one-shot process has stopped before returning a result
    // to the persistent Worker.
    try {
      if ((await workspaceUsage(baseRequest.workingDirectory)).exceeded) {
        workspaceLimitExceeded = true;
        workspaceLimitReason ||= "post_stop_exceeded";
      }
    } catch (error) {
      workspaceLimitExceeded = true;
      workspaceLimitReason ||= `post_stop_error:${error?.code || error?.name || "unknown"}`;
    }
    processHandle.dispose();
    let stdoutText = Buffer.concat(stdout).toString("utf8");
    if (markerExitCode !== null) {
      const markerIndex = stdoutText.indexOf(marker);
      if (markerIndex >= 0) {
        let lineStart = stdoutText.lastIndexOf("\n", markerIndex);
        const lineEnd = stdoutText.indexOf("\n", markerIndex);
        if (lineStart > 0 && stdoutText[lineStart - 1] === "\r") lineStart -= 1;
        stdoutText = stdoutText.slice(0, Math.max(0, lineStart)) + stdoutText.slice(lineEnd < 0 ? stdoutText.length : lineEnd + 1);
      }
    }
    const stderrText = Buffer.concat(stderr)
      .toString("utf8")
      .split(/\r?\n/)
      .filter((line) => !(line.startsWith("Failed to find real location of ") && line.endsWith("python.exe")))
      .join("\n");
    return {
      stdout: stdoutText,
      stderr: stderrText,
      returncode: timedOut ? null : markerExitCode ?? (Number.isInteger(terminal?.exitCode) ? terminal.exitCode : 1),
      timeout: timedOut,
      output_truncated: outputTruncated,
      workspace_limit_exceeded: workspaceLimitExceeded,
      workspace_limit_reason: workspaceLimitReason,
      execution_incomplete: executionIncomplete,
      process_tree_unverified: processTreeUnverified,
      process_tree_failure_reason: processTreeFailureReason,
    };
  } finally {
    clearInterval(workspaceMonitor);
    await workspaceMonitorPromise;
    if (processHandle) {
      try { processHandle.kill(); } catch {}
      try { processHandle.dispose(); } catch {}
    }
    try { fs.unlinkSync(scriptPath); } catch {}
  }
}

async function serveWorker() {
  const config = await readHostConfig();
  const required = ["workspace", "pythonExe", "pythonRoot", "pythonEnvRoot", "workerScript", "helperRoot"];
  for (const key of required) {
    if (typeof config[key] !== "string" || !path.isAbsolute(config[key])) {
      throw new Error(`invalid host worker configuration: ${key}`);
    }
  }
  // Linux firewall helpers live in sbin on distributions whose sanitized
  // host PATH only includes bin. These are fixed system directories, never
  // paths supplied by a project or by the model.
  if (process.platform === "linux") {
    process.env.PATH = `${process.env.PATH || ""}:/usr/sbin:/sbin`;
  }
  const { spawn } = await import("@microsoft/mxc-sdk/v1");
  const workspace = path.resolve(config.workspace);
  const pythonRoot = path.resolve(config.pythonRoot);
  const pythonEnvRoot = path.resolve(config.pythonEnvRoot);
  const helperRoot = path.resolve(config.helperRoot);
  const readwritePaths = [workspace];
  const readonlyPaths = [pythonRoot, pythonEnvRoot, helperRoot];
  if (process.platform === "win32") {
    readonlyPaths.push(path.join(process.env.SystemRoot || "C:/Windows", "System32"));
  } else if (process.platform === "linux" && process.arch === "x64") {
    readonlyPaths.push("/usr", "/lib", "/lib64", "/etc/ld.so.cache");
  } else if (process.platform === "darwin" && process.arch === "arm64") {
    // Darwin dyld and Python must read the system's code resources; never
    // recursively expose user home, arbitrary /Library or /opt/homebrew.
    readonlyPaths.push("/System/Library", "/usr/lib", "/usr/bin", "/bin");
  } else {
    throw new Error("MXC worker is unsupported on this host platform");
  }
  const deniedPaths = Array.isArray(config.deniedPaths)
    ? config.deniedPaths.filter((item) => typeof item === "string" && path.isAbsolute(item))
    : [];
  const windowsRoot = process.env.SystemRoot || "C:/Windows";
  const environment = process.platform === "win32" ? {
    SystemRoot: windowsRoot,
    WINDIR: process.env.WINDIR || windowsRoot,
    PATH: `${path.join(windowsRoot, "System32")};${pythonRoot};${pythonEnvRoot}`,
    LOCALAPPDATA: path.join(workspace, ".localappdata"),
    APPDATA: path.join(workspace, ".appdata"),
    TEMP: path.join(workspace, ".temp"),
    TMP: path.join(workspace, ".temp"),
    HOME: workspace,
    USERPROFILE: workspace,
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONNOUSERSITE: "1",
    PYTHONIOENCODING: "utf-8",
    UAGENT_AUTO_INSTALL: "0",
    UAGENT_SESSION_STORE: "0",
  } : {
    HOME: path.join(workspace, ".home"),
    PATH: `${path.join(pythonEnvRoot, "bin")}:${path.join(pythonRoot, "bin")}` + ":/usr/bin:/bin",
    LANG: "C.UTF-8",
    TMPDIR: path.join(workspace, ".temp"),
    TEMP: path.join(workspace, ".temp"),
    TMP: path.join(workspace, ".temp"),
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONNOUSERSITE: "1",
    PYTHONIOENCODING: "utf-8",
    UAGENT_AUTO_INSTALL: "0",
    UAGENT_SESSION_STORE: "0",
  };
  const workerDirs = process.platform === "win32"
    ? [environment.LOCALAPPDATA, environment.APPDATA, environment.TEMP]
    : [environment.HOME, environment.TMPDIR];
  for (const directory of workerDirs) {
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    if (process.platform === "linux") fs.chmodSync(directory, 0o700);
  }
  const baseRequest = {
    workingDirectory: workspace,
    containment: {
      type: process.platform === "win32"
        ? "processcontainer"
        : process.platform === "darwin" ? "seatbelt" : "process",
    },
    ...(process.platform === "win32" ? { fallback: { allowDaclMutation: false } } : {}),
    filesystem: { readwritePaths, readonlyPaths, deniedPaths },
    // Keep host loopback isolated. Windows requires private-network ingress
    // capability for LAN egress; Bubblewrap cannot allow ingress at all.
    network: {
      egress: { default: "allow" },
      ingress: { default: process.platform === "win32" ? "allow" : "deny", hostLoopback: "deny" },
    },
    ui: { disable: true },
    inheritDefaultEnvironment: false,
    environment,
  };
  const command = `${quoteArgument(config.pythonExe)} -I -X utf8 -u ${quoteArgument(config.workerScript)}`;
  const processHandle = await spawn({
    ...baseRequest,
    command,
    timeoutMs: MAX_SESSION_MS,
  });
  const stdin = processHandle.standardInput;
  const stdout = processHandle.standardOutput;
  const stderr = processHandle.standardError;
  if (!stdin || !stdout || !stderr) {
    processHandle.kill();
    await processHandle.wait();
    processHandle.dispose();
    throw new Error("MXC ProcessContainer did not provide all three IPC pipes");
  }
  stderr.resume();
  const nextReply = createReplyQueue(stdout, processHandle);
  const waitPromise = processHandle.wait();
  let closed = false;
  const stopWorker = async () => {
    if (closed) return;
    closed = true;
    try { processHandle.kill(); } catch {}
    try { await Promise.race([waitPromise, new Promise((resolve) => setTimeout(resolve, 5_000))]); } catch {}
    try { processHandle.dispose(); } catch {}
  };
  let startup;
  try {
    startup = await nextReply(15_000);
    if (!startup || startup.ready !== true) throw new Error("sandbox worker failed its startup handshake");
  } catch (error) {
    await stopWorker();
    throw error;
  }
  writeHost({
    ready: true,
    backend: process.platform === "win32"
      ? "mxc-processcontainer"
      : process.platform === "darwin" ? "mxc-seatbelt" : "mxc-bubblewrap",
  });
  const hostLines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  process.stdin.on("close", () => { void stopWorker(); });
  process.stdin.on("error", () => { void stopWorker(); });
  try {
    for await (const line of hostLines) {
      if (Buffer.byteLength(line, "utf8") > MAX_FRAME_BYTES) throw new Error("host request frame is too large");
      const request = JSON.parse(line);
      if (request.operation === "close") {
        await stopWorker();
        writeHost({ ok: true, closed: true });
        break;
      }
      if (request.operation !== "run" || typeof request.payload !== "object" || request.payload === null) {
        writeHost({ ok: false, error: "invalid sandbox IPC request" });
        continue;
      }
      if (request.payload.name === "python_exec") {
        try {
          const result = await executePythonInContainer(
            config,
            baseRequest,
            request.payload.args || {},
            spawn,
          );
          if (result.process_tree_unverified) {
            writeHost({ ok: false, terminate: true, error: `Python process tree termination could not be verified (${result.process_tree_failure_reason || "unknown"}); the isolated worker was terminated` });
            await stopWorker();
            break;
          }
          if (result.workspace_limit_exceeded) {
            writeHost({ ok: false, terminate: true, error: `session workspace limit exceeded (${result.workspace_limit_reason || "unknown"}); the isolated worker was terminated` });
            await stopWorker();
            break;
          }
          if (result.execution_incomplete) {
            writeHost({ ok: false, error: "Python execution exited before its completion marker" });
            continue;
          }
          writeHost({ ok: true, result });
        } catch (error) {
          writeHost({ ok: false, error: `${error?.name || "Error"}: ${error?.message || error}` });
        }
        continue;
      }
      const reply = nextReply(HARD_EXECUTION_TIMEOUT_MS + 5_000);
      stdin.write(`${JSON.stringify(request.payload)}\n`);
      const result = await reply;
      let usage;
      try { usage = await workspaceUsage(workspace); } catch { usage = { exceeded: true }; }
      if (usage.exceeded) {
        writeHost({ ok: false, terminate: true, error: "session workspace limit exceeded; the isolated worker was terminated" });
        await stopWorker();
        break;
      }
      writeHost(result);
      if (result?.terminate === true) {
        await stopWorker();
        break;
      }
    }
  } finally {
    await stopWorker();
    hostLines.close();
  }
}

if (process.argv[2] === "probe") {
  try { await probeHost(); } catch (error) {
    writeHost({ ok: false, error: `${error?.name || "Error"}: ${error?.message || error}` });
    process.exitCode = 2;
  }
} else if (process.argv[2] === "worker") {
  try { await serveWorker(); } catch (error) {
    writeHost({ ok: false, error: `${error?.name || "Error"}: ${error?.message || error}` });
    process.exitCode = 2;
  }
} else {
  writeHost({ ok: false, error: "expected probe or worker mode" });
  process.exitCode = 2;
}
