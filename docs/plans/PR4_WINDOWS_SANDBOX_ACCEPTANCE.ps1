[CmdletBinding()]
param(
    [string]$RuntimeDir = (Join-Path $env:LOCALAPPDATA 'uagent\mxc_runtime'),
    [switch]$RunVmTests
)

$ErrorActionPreference = 'Stop'

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
        [switch]$DryRun
    )

    $arguments = @('--experimental')
    if ($DryRun) {
        $arguments += '--dry-run'
    }
    $arguments += $ConfigPath
    $output = (& $Executor @arguments 2>&1 | Out-String)
    $exitCode = $LASTEXITCODE
    $decoded = Get-ProcessOutputText -Text $output
    [pscustomobject]@{
        ExitCode = $exitCode
        Output = $decoded
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
    $activeSandbox = @(Get-Process -Name 'WindowsSandbox*' -ErrorAction SilentlyContinue)
    if ($activeSandbox.Count -gt 0) {
        throw 'A Windows Sandbox process is already active in this logon session; refusing to overlap VMs.'
    }
}

$workRoot = Join-Path ([IO.Path]::GetTempPath()) ("uag-pr4-wsb-" + [guid]::NewGuid().ToString('N'))
$workspace = Join-Path $workRoot 'scope-workspace'
$configDir = Join-Path $workRoot 'requests'
$hostCanary = Join-Path $workRoot 'host-only-canary.txt'
New-Item -ItemType Directory -Path $workspace, $configDir -Force | Out-Null
Set-Content -LiteralPath $hostCanary -Value 'UAG_PR4_HOST_CANARY_MUST_NOT_BE_VISIBLE' -NoNewline

try {
    $config = [ordered]@{
        version = '1.1.0-alpha'
        containment = 'windows_sandbox'
        process = [ordered]@{
            commandLine = 'powershell.exe -NoLogo -NoProfile -NonInteractive -Command Write-Output UAG_PR4_VM_SMOKE'
            timeout = 30000
        }
        filesystem = [ordered]@{
            readwritePaths = @($workspace)
            readonlyPaths = @()
        }
    }

    $configPath = Join-Path $configDir 'windows-sandbox-smoke.json'
    $json = $config | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($configPath, $json, [Text.UTF8Encoding]::new($false))
    $dryRun = Invoke-WxcConfig -Executor $executor -ConfigPath $configPath -DryRun
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

    # Sequential one-shot invocations only: MXC Windows Sandbox supports one VM
    # per logon session. Do not run this acceptance script concurrently.
    $smoke = Invoke-WxcConfig -Executor $executor -ConfigPath $configPath
    if ($smoke.ExitCode -ne 0 -or $smoke.Output -notmatch 'UAG_PR4_VM_SMOKE') {
        throw "Real Windows Sandbox smoke execution failed. Output:`n$($smoke.Output)"
    }
    Write-Output 'Real VM smoke command completed; retain the complete executor diagnostics for review.'

    $escapedCanary = $hostCanary.Replace("'", "''")
    $canaryCommand = "`$p='$escapedCanary'; if (Test-Path -LiteralPath `$p) { Write-Output UAG_PR4_HOST_PATH_VISIBLE; exit 9 } else { Write-Output UAG_PR4_HOST_PATH_BLOCKED; exit 0 }"
    $config['process']['commandLine'] = "powershell.exe -NoLogo -NoProfile -NonInteractive -Command `"$canaryCommand`""
    $configPath = Join-Path $configDir 'host-path-denial.json'
    $json = $config | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($configPath, $json, [Text.UTF8Encoding]::new($false))
    $canaryDryRun = Invoke-WxcConfig -Executor $executor -ConfigPath $configPath -DryRun
    if ($canaryDryRun.ExitCode -ne 0 -or $canaryDryRun.Output -notmatch 'Dry run completed\. Result: validation passed') {
        throw "Host-path denial request failed dry-run validation. Output:`n$($canaryDryRun.Output)"
    }
    $canary = Invoke-WxcConfig -Executor $executor -ConfigPath $configPath
    if ($canary.ExitCode -ne 0 -or $canary.Output -notmatch 'UAG_PR4_HOST_PATH_BLOCKED' -or $canary.Output -match 'UAG_PR4_HOST_PATH_VISIBLE|UAG_PR4_HOST_CANARY_MUST_NOT_BE_VISIBLE') {
        throw "Host-only canary was visible or the negative test failed. Output:`n$($canary.Output)"
    }
    Write-Output 'Host-only canary denial check passed.'
    Write-Warning 'This script is a smoke/host-path check only; it does not establish full PR4 acceptance or Remote eligibility.'
    Write-Warning 'Complete the resource-limit, network, credential, lifecycle, multi-scope, export, and Browser/Computer Use matrix in PR4_WINDOWS_SANDBOX_ACCEPTANCE.md.'
}
finally {
    if (Test-Path -LiteralPath $workRoot) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
}
