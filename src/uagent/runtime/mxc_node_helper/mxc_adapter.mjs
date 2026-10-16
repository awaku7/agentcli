import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";

const MAX_FRAME_BYTES = 1_100_000;
const HARD_EXECUTION_TIMEOUT_MS = 60_000;
const MAX_SESSION_MS = 12 * 60 * 60 * 1000;
const MAX_WORKSPACE_BYTES = 256 * 1024 * 1024;
const MAX_WORKSPACE_ENTRIES = 5_000;
const PYTHON_OUTPUT_LIMIT = 64 * 1024;

function writeHost(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function quoteWindowsArgument(value) {
  const text = String(value);
  return `"${text.replace(/(\\*)"/g, "$1$1\\\"").replace(/(\\+)$/g, "$1$1")}"`;
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
  if (process.platform !== "win32" || process.arch !== "x64") {
    writeHost({ ok: false, error: "MXC ProcessContainer supports only verified Windows x64 in this release" });
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
  "$items = @((Get-Item -LiteralPath $root -Force)) + @(Get-ChildItem -LiteralPath $root -Force -Recurse -ErrorAction Stop)",
  "[long]$total = 0",
  "[long]$streamCount = 0",
  "foreach ($item in $items) {",
  "  if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }",
  "  $streamData = New-Object UagentMxcStreamScan+Data",
  "  $handle = [UagentMxcStreamScan]::FindFirstStreamW($item.FullName, 0, [ref]$streamData, 0)",
  "  if ($handle -eq [IntPtr](-1)) {",
  "    $winError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()",
  "    if ($winError -ne 38) { throw \"FindFirstStreamW failed: $winError\" }",
  "    continue",
  "  }",
  "  try {",
  "    do {",
  "      if ($streamData.StreamName -ne '::$DATA') {",
  "        $total += [long]$streamData.StreamSize",
  "        $streamCount += 1",
  "      }",
  "      $hasNext = [UagentMxcStreamScan]::FindNextStreamW($handle, [ref]$streamData)",
  "    } while ($hasNext)",
  "    $winError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()",
  "    if ($winError -ne 38) { throw \"FindNextStreamW failed: $winError\" }",
  "  } finally { [void][UagentMxcStreamScan]::FindClose($handle) }",
  "}",
  "[Console]::Out.WriteLine(('{0},{1}' -f $total.ToString([Globalization.CultureInfo]::InvariantCulture), $streamCount.ToString([Globalization.CultureInfo]::InvariantCulture)))",
].join("\n");

function alternateStreamUsage(root) {
  const systemRoot = process.env.SystemRoot || process.env.WINDIR || String.raw`C:\Windows`;
  const powershell = path.join(systemRoot, "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
  const output = execFileSync(
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

function workspaceUsage(root) {
  let bytes = 0;
  let entries = 0;
  const resolvedRoot = path.resolve(root).toLowerCase();
  const rootPrefix = `${path.resolve(root)}${path.sep}`.toLowerCase();
  const pending = [path.resolve(root)];
  while (pending.length) {
    const entry = pending.pop();
    const stat = fs.lstatSync(entry);
    if (stat.isSymbolicLink()) continue;
    const resolved = fs.realpathSync(entry).toLowerCase();
    if (resolved !== resolvedRoot && !resolved.startsWith(rootPrefix)) {
      return { exceeded: true, bytes, entries };
    }
    if (stat.isDirectory()) {
      const directory = fs.opendirSync(entry);
      try {
        let child;
        while ((child = directory.readSync()) !== null) {
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
  const alternate = alternateStreamUsage(root);
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
  // makes this marker prove that user cleanup has completed before we kill the
  // one-shot container and reap any remaining child processes.
  const wrapper = [
    "import atexit, sys, traceback",
    "__uag_stdout = sys.stdout",
    `__uag_source = ${JSON.stringify(code)}`,
    `__uag_marker = ${JSON.stringify(marker)}`,
    "__uag_exit = 0",
    "def __uag_emit_marker():",
    "    __uag_stdout.write(chr(10) + __uag_marker + ':' + str(__uag_exit) + chr(10))",
    "    __uag_stdout.flush()",
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
  let workspaceMonitor;
  let processHandle;
  try {
    const command = `${quoteWindowsArgument(config.pythonExe)} -I -X utf8 -u ${quoteWindowsArgument(scriptPath)}`;
    processHandle = await spawnMxc({ ...baseRequest, command, timeoutMs: 35_000 });
    workspaceMonitor = setInterval(() => {
      if (workspaceLimitExceeded) return;
      try {
        if (workspaceUsage(baseRequest.workingDirectory).exceeded) {
          workspaceLimitExceeded = true;
          processHandle.kill();
        }
      } catch {
        workspaceLimitExceeded = true;
        try { processHandle.kill(); } catch {}
      }
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
    clearInterval(markerPoll);
    const timedOut = outcome.kind === "timeout";
    try { processHandle.kill(); } catch {}
    // Keep quota monitoring through user shutdown handlers and until kill is
    // requested, but do not scan a process tree while the container is tearing down.
    clearInterval(workspaceMonitor);
    let stopTimer;
    const processStopped = await Promise.race([
      waitPromise.then(() => true, () => true),
      new Promise((resolve) => { stopTimer = setTimeout(() => resolve(false), 5_000); }),
    ]);
    clearTimeout(stopTimer);
    clearTimeout(executionTimer);
    if (!processStopped) workspaceLimitExceeded = true;
    // The interval is only a watchdog; it may not fire if Python exits quickly.
    // Recheck synchronously after the one-shot process has been stopped before
    // returning a result to the persistent Worker.
    try {
      if (workspaceUsage(baseRequest.workingDirectory).exceeded) {
        workspaceLimitExceeded = true;
      }
    } catch {
      workspaceLimitExceeded = true;
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
    const terminal = outcome.terminal;
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
    };
  } finally {
    clearInterval(workspaceMonitor);
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
  const { spawn } = await import("@microsoft/mxc-sdk/v1");
  const workspace = path.resolve(config.workspace);
  const pythonRoot = path.resolve(config.pythonRoot);
  const pythonEnvRoot = path.resolve(config.pythonEnvRoot);
  const helperRoot = path.resolve(config.helperRoot);
  const readwritePaths = [workspace];
  const readonlyPaths = [
    pythonRoot,
    pythonEnvRoot,
    helperRoot,
    path.join(process.env.SystemRoot || "C:\\Windows", "System32"),
  ];
  const deniedPaths = Array.isArray(config.deniedPaths)
    ? config.deniedPaths.filter((item) => typeof item === "string" && path.isAbsolute(item))
    : [];
  const environment = {
    SystemRoot: process.env.SystemRoot || "C:\\Windows",
    WINDIR: process.env.WINDIR || process.env.SystemRoot || "C:\\Windows",
    PATH: `${path.join(process.env.SystemRoot || "C:\\Windows", "System32")};${pythonRoot};${pythonEnvRoot}`,
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
  };
  for (const directory of [environment.LOCALAPPDATA, environment.APPDATA, environment.TEMP]) {
    fs.mkdirSync(directory, { recursive: true });
  }
  const baseRequest = {
    workingDirectory: workspace,
    containment: { type: "processcontainer" },
    fallback: { allowDaclMutation: false },
    filesystem: { readwritePaths, readonlyPaths, deniedPaths },
    network: {
      egress: { default: "deny" },
      ingress: { default: "deny", hostLoopback: "deny" },
    },
    ui: { disable: true },
    inheritDefaultEnvironment: false,
    environment,
  };
  const command = `${quoteWindowsArgument(config.pythonExe)} -I -X utf8 -u ${quoteWindowsArgument(config.workerScript)}`;
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
  writeHost({ ready: true, backend: "mxc-processcontainer" });
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
          if (result.workspace_limit_exceeded) {
            writeHost({ ok: false, error: "session workspace limit exceeded; the isolated worker was terminated" });
            await stopWorker();
            break;
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
      try { usage = workspaceUsage(workspace); } catch { usage = { exceeded: true }; }
      if (usage.exceeded) {
        writeHost({ ok: false, error: "session workspace limit exceeded; the isolated worker was terminated" });
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
