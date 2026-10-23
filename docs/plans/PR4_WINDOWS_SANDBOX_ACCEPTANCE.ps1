[CmdletBinding()]
param(
    [string]$RuntimeDir = (Join-Path $env:LOCALAPPDATA 'uagent\mxc_runtime'),
    [switch]$RunVmTests,
    [string]$DiagnosticsDir = (Join-Path $env:LOCALAPPDATA 'uagent\pr4_acceptance')
)

$ErrorActionPreference = 'Stop'
$runId = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $DiagnosticsDir -Force | Out-Null
$diagnosticPath = Join-Path $DiagnosticsDir "wxc-exec-$runId.log"
[IO.File]::WriteAllText($diagnosticPath, "PR4 Windows Sandbox acceptance diagnostics`nRun ID: $runId`n", [Text.UTF8Encoding]::new($false))
Write-Output "Executor diagnostics will be saved to: $diagnosticPath"

function Get-ProcessOutputText {
    param([string]$Text)

    $decoded = $Text
    foreach ($line in ($Text -split "`r?`n")) {
        $candidate = $line.Trim()
        if ($candidate -match '^[A-Za-z0-9+/]{16,}[A-Za-z0-9+/=]*$') {
            try {
                $bytes = [Convert]::FromBase64String($candidate)
                $decoded += "`n" + [Text.Encoding]::UTF8.GetString($bytes)
            }
            catch {
                # Ordinary diagnostic lines are not base64 output.
            }
        }
    }
    return $decoded
}

function Invoke-WxcConfig {
    param(
        [string]$Executor,
        [string]$ConfigPath,
        [string]$LogPath,
        [switch]$DryRun
    )

    $arguments = @('--experimental', '--debug', '--log-file', $LogPath)
    if ($DryRun) {
        $arguments += '--dry-run'
    }
    $arguments += $ConfigPath
    $output = (& $Executor @arguments 2>&1 | Out-String)
    $exitCode = $LASTEXITCODE
    $decoded = Get-ProcessOutputText -Text $output
    $logEntry = @"

===== WXC EXECUTION =====
Config: $ConfigPath
DryRun: $([bool]$DryRun)
ExitCode: $exitCode
--- Raw executor output ---
$output
--- Decoded executor output ---
$decoded
===== END WXC EXECUTION =====
"@
    [IO.File]::AppendAllText($LogPath, $logEntry + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    [pscustomobject]@{
        ExitCode = $exitCode
        Output = $decoded
    }
}

function Get-ActiveSandboxProcesses {
    # MXC's Windows Sandbox reference treats WindowsSandbox* host processes as
    # ownership targets. SYSTEM-owned vmmem* residuals are not ownership targets
    # and do not block a new launch once the WindowsSandbox* processes exit.
    @(Get-Process -Name 'WindowsSandbox*' -ErrorAction SilentlyContinue)
}

function Get-WxcWorkloadResult {
    param([string]$Text)

    # --debug echoes the request (including the command string) before the
    # actual guest result. Parse markers only after the guest exit-code line.
    $matches = [regex]::Matches($Text, '(?m)^Exit code:\s*(?<code>\d+)(?:\s+\([^)]+\))?\s*$')
    if ($matches.Count -eq 0) {
        return $null
    }
    $match = $matches[$matches.Count - 1]
    $resultText = $Text.Substring($match.Index + $match.Length).TrimStart([char]13, [char]10)
    [pscustomobject]@{
        ExitCode = [int]$match.Groups['code'].Value
        Output = $resultText
    }
}

$manifestPath = Join-Path $RuntimeDir 'node_modules\@microsoft\mxc-sdk\package.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.version -ne '1.0.0') {
    throw "Expected pinned @microsoft/mxc-sdk 1.0.0; found '$($manifest.version)'"
}

$executor = Join-Path $RuntimeDir 'node_modules\@microsoft\mxc-sdk\bin\x64\wxc-exec.exe'
if (-not (Test-Path -LiteralPath $executor -PathType Leaf)) {
    throw "Pinned x64 wxc-exec.exe is missing: $executor"
}
$help = (& $executor --help 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $help -notmatch '--experimental' -or $help -notmatch '--dry-run') {
    throw 'The pinned executor does not expose the expected experimental/dry-run CLI contract.'
}

$edition = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').EditionID
$windowsBuild = [Environment]::OSVersion.Version.Build
$isWin11 = $windowsBuild -ge 22000
$isProOrEnterprise = $edition -match 'Professional|Enterprise|Education'
if ($RunVmTests -and (-not $isWin11 -or -not $isProOrEnterprise)) {
    throw "VM acceptance requires Windows 11 Pro/Enterprise/Education; build='$windowsBuild', EditionID='$edition'."
}
if ($RunVmTests) {
    $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run -RunVmTests from an elevated PowerShell session; no VM was started.'
    }
    $freeMemoryMb = [math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024)
    if ($freeMemoryMb -lt 2048) {
        throw "VM acceptance needs at least 2048 MB free memory; found ${freeMemoryMb} MB. No VM was started."
    }
    $activeSandbox = @(Get-ActiveSandboxProcesses)
    if ($activeSandbox.Count -gt 0) {
        $activeNames = ($activeSandbox | ForEach-Object { '{0} (PID {1})' -f $_.ProcessName, $_.Id }) -join ', '
        throw "A Windows Sandbox VM process is already active in this logon session ($activeNames); refusing to overlap VMs."
    }
}

$workRoot = Join-Path ([IO.Path]::GetTempPath()) ("uag-pr4-wsb-" + [guid]::NewGuid().ToString('N'))
$workspace = Join-Path $workRoot 'scope-workspace'
$configDir = Join-Path $workRoot 'requests'
$hostCanary = Join-Path $workRoot 'host-only-canary.txt'
New-Item -ItemType Directory -Path $workspace, $configDir -Force | Out-Null
Set-Content -LiteralPath $hostCanary -Value 'UAG_PR4_HOST_CANARY_MUST_NOT_BE_VISIBLE' -NoNewline

try {
    $escapedCanary = $hostCanary.Replace("'", "''")
    $vmCommand = "Write-Output UAG_PR4_VM_SMOKE; `$p='$escapedCanary'; if (Test-Path -LiteralPath `$p) { Write-Output UAG_PR4_HOST_PATH_VISIBLE; exit 9 } else { Write-Output UAG_PR4_HOST_PATH_BLOCKED; exit 0 }"

    $config = [ordered]@{
        version = '1.1.0-alpha'
        containment = 'windows_sandbox'
        process = [ordered]@{
            commandLine = "powershell.exe -NoLogo -NoProfile -NonInteractive -Command `"$vmCommand`""
            timeout = 30000
        }
        fallback = [ordered]@{
            allowDaclMutation = $false
        }
        filesystem = [ordered]@{
            readwritePaths = @($workspace)
            readonlyPaths = @()
        }
    }

    $configPath = Join-Path $configDir 'windows-sandbox-smoke.json'
    $json = $config | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($configPath, $json, [Text.UTF8Encoding]::new($false))
    $dryRun = Invoke-WxcConfig -Executor $executor -ConfigPath $configPath -LogPath $diagnosticPath -DryRun
    if ($dryRun.ExitCode -ne 0 -or $dryRun.Output -notmatch 'Dry run completed\. Result: validation passed') {
        if ($RunVmTests) {
            throw "Executor dry-run did not validate the pinned Windows Sandbox request. Output:`n$($dryRun.Output)"
        }
        Write-Warning "Dry-run did not prove Windows Sandbox support on this host; no VM was started. Output:`n$($dryRun.Output)"
        Write-Output "Host EditionID: $edition"
        Write-Output 'This result is not a capability pass and cannot enable Remote execution.'
        return
    }

    Write-Output 'MXC request contract dry-run passed.'
    Write-Output 'This is not evidence of VM isolation, resource enforcement, or Remote eligibility.'
    if (-not $RunVmTests) {
        Write-Output 'No VM was started. Re-run with -RunVmTests only on a dedicated Windows Pro/Enterprise acceptance host.'
        return
    }

    $feature = (& dism.exe /English /online /Get-FeatureInfo /FeatureName:Containers-DisposableClientVM 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $feature -notmatch 'State\s*:\s*Enabled') {
        throw 'Windows Sandbox feature Containers-DisposableClientVM is not enabled.'
    }

    # Keep the positive smoke and host-path denial check in one VM invocation.
    # MXC Windows Sandbox supports one VM per logon session.
    $vm = Invoke-WxcConfig -Executor $executor -ConfigPath $configPath -LogPath $diagnosticPath
    $guest = Get-WxcWorkloadResult -Text $vm.Output
    $guestExitCode = if ($null -ne $guest) { $guest.ExitCode } else { -1 }
    $guestOutput = if ($null -ne $guest) { $guest.Output } else { '' }
    if ($vm.ExitCode -ne 0 -or
        $guestExitCode -ne 0 -or
        $guestOutput -notmatch 'UAG_PR4_VM_SMOKE' -or
        $guestOutput -notmatch 'UAG_PR4_HOST_PATH_BLOCKED' -or
        $guestOutput -match 'UAG_PR4_HOST_PATH_VISIBLE|UAG_PR4_HOST_CANARY_MUST_NOT_BE_VISIBLE') {
        throw "Windows Sandbox smoke/host-path denial check failed. Executor exit=$($vm.ExitCode), guest exit=$guestExitCode. Guest output:`n$guestOutput`nFull diagnostics: $diagnosticPath"
    }
    Write-Output 'Real Windows Sandbox smoke command completed; retain the complete executor diagnostics for review.'
    Write-Output 'Host-only canary denial check passed.'
    Write-Output "Executor diagnostics: $diagnosticPath"
    Write-Warning 'This script is a smoke/host-path check only; it does not establish full PR4 acceptance or Remote eligibility.'
    Write-Warning 'Complete the resource-limit, network, credential, lifecycle, multi-scope, export, and Browser/Computer Use matrix in PR4_WINDOWS_SANDBOX_ACCEPTANCE.md.'
}
finally {
    if (Test-Path -LiteralPath $workRoot) {
        if ($RunVmTests) {
            # wxc-exec may return after the guest command completes while the
            # WindowsSandbox host process is still shutting down. MXC documents
            # vmmemWindowsSandbox as a non-owning residual, not a VM owner.
            $shutdownWaitSeconds = 120
            $shutdownStart = Get-Date
            $shutdownDeadline = $shutdownStart.AddSeconds($shutdownWaitSeconds)
            $nextStatus = $shutdownStart
            do {
                $activeSandbox = @(Get-ActiveSandboxProcesses)
                if ($activeSandbox.Count -eq 0) {
                    break
                }
                $now = Get-Date
                if ($now -ge $nextStatus) {
                    $elapsed = [math]::Floor(($now - $shutdownStart).TotalSeconds)
                    Write-Output "Waiting for Windows Sandbox shutdown... ${elapsed}s elapsed."
                    $nextStatus = $now.AddSeconds(30)
                }
                Start-Sleep -Seconds 2
            } while ((Get-Date) -lt $shutdownDeadline)

            if ($activeSandbox.Count -gt 0) {
                $activeNames = ($activeSandbox | ForEach-Object { '{0} (PID {1})' -f $_.ProcessName, $_.Id }) -join ', '
                $cleanupMessage = "Acceptance incomplete: WindowsSandbox host process(es) remain after the $shutdownWaitSeconds-second shutdown wait ($activeNames). Workspace preserved at '$workRoot'. Diagnostics: $diagnosticPath"
                [IO.File]::AppendAllText($diagnosticPath, "`n$cleanupMessage`n", [Text.UTF8Encoding]::new($false))
                Write-Warning $cleanupMessage
                throw $cleanupMessage
            }
        }

        # Retry briefly for transient filesystem scanners, but never force-kill
        # a process or delete the workspace while it is still in use.
        $cleanupDeadline = (Get-Date).AddSeconds(20)
        $cleanupError = $null
        do {
            try {
                if (Test-Path -LiteralPath $workRoot) {
                    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction Stop
                }
                $cleanupError = $null
                break
            }
            catch {
                $cleanupError = $_
                if ((Get-Date) -lt $cleanupDeadline) {
                    Start-Sleep -Seconds 2
                }
            }
        } while ((Get-Date) -lt $cleanupDeadline)

        if ($null -ne $cleanupError) {
            $cleanupMessage = "Acceptance incomplete: temporary workspace cleanup failed at '$workRoot' after bounded retries. Error: $($cleanupError.Exception.Message). Workspace preserved if still present. Diagnostics: $diagnosticPath"
            [IO.File]::AppendAllText($diagnosticPath, "`n$cleanupMessage`n", [Text.UTF8Encoding]::new($false))
            Write-Warning $cleanupMessage
            throw $cleanupMessage
        }

        try {
            [IO.File]::AppendAllText($diagnosticPath, "`nWorkspace cleanup succeeded: $workRoot`n", [Text.UTF8Encoding]::new($false))
            Write-Output "Temporary test workspace cleaned: $workRoot"
        }
        catch {
            Write-Warning "Workspace was removed, but the cleanup success record could not be appended to diagnostics: $($_.Exception.Message)"
        }
    }
}
