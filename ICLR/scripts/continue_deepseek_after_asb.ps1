param(
    [string]$Root = "",
    [string]$AsbRoot = "",
    [string]$WorkspaceRoot = "",
    [string]$WorkspaceAblationRoot = "",
    [string]$WorkspaceManifest = "",
    [string]$AblationRoot = "",
    [int]$PollSeconds = 60
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if ([string]::IsNullOrWhiteSpace($AsbRoot)) {
    $AsbRoot = Join-Path $Root "ICLR\results\asb_200_rr_source_trust_strong_baselines_deepseek_v1"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $Root "ICLR\results\autodojo_v122_workspace_14x14_deepseek_v1"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceAblationRoot)) {
    $WorkspaceAblationRoot = Join-Path $Root "ICLR\results\autodojo_v122_workspace_14x14_clafr_paper_ablation_v1"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceManifest)) {
    $WorkspaceManifest = Join-Path $WorkspaceRoot "split_manifest.json"
}
if ([string]::IsNullOrWhiteSpace($AblationRoot)) {
    $AblationRoot = Join-Path $Root "ICLR\results\autodojo_table_clafr_paper_ablation_full_v1"
}

$LogDir = Join-Path $Root "ICLR\results\pipeline_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("continue_deepseek_after_asb_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Output $line
}

function Set-RunEnvironment {
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:NO_COLOR = "1"
    $env:TERM = "dumb"
    $env:PYTHONPATH = (
        "agentdojo\src;agentdojo\variant_generation;" +
        (Join-Path $Root "ICLR\src") + ";" +
        (Join-Path $Root "src") + ";" +
        $Root
    )
}

function Invoke-CheckedPython {
    param([string[]]$Arguments)
    Write-Log ("python " + ($Arguments -join " "))
    & python @Arguments 2>&1 | Tee-Object -FilePath $LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

function Get-AsbPid {
    $pidPath = Join-Path $AsbRoot "run.pid"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        return $null
    }
    $raw = (Get-Content -LiteralPath $pidPath -Raw).Trim()
    if (-not $raw) {
        return $null
    }
    return [int]$raw
}

function Wait-AsbProcess {
    $asbPid = Get-AsbPid
    if ($null -eq $asbPid) {
        Write-Log "No ASB run.pid found; continuing to aggregation gate."
        return
    }
    Write-Log "Waiting for ASB PID $asbPid to exit."
    while ($true) {
        $process = Get-Process -Id $asbPid -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            Write-Log "ASB PID $asbPid exited."
            return
        }
        Start-Sleep -Seconds $PollSeconds
    }
}

function Test-AsbComplete {
    $summaryPath = Join-Path $AsbRoot "asb_summary.csv"
    if (-not (Test-Path -LiteralPath $summaryPath)) {
        return $false
    }
    $rows = Import-Csv -LiteralPath $summaryPath
    if ($rows.Count -eq 0) {
        return $false
    }
    foreach ($row in $rows) {
        if ([int]$row.cases -ne [int]$row.expected_cases) {
            Write-Log ("ASB incomplete: {0} {1}/{2}" -f $row.variant, $row.cases, $row.expected_cases)
            return $false
        }
        if ([string]$row.complete -notin @("True", "true", "1")) {
            Write-Log ("ASB incomplete flag: {0} complete={1}" -f $row.variant, $row.complete)
            return $false
        }
    }
    return $true
}

function Assert-NoBenchmarkProcess {
    $currentPid = $PID
    $active = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $currentPid -and
        $_.CommandLine -match "run_asb_clafr_agent_score|run_autodojo_workspace_slice|agentdojo\.scripts\.benchmark|run_autodojo_table_clafr"
    }
    if ($active) {
        $active | ForEach-Object { Write-Log ("Still active: PID {0} {1}" -f $_.ProcessId, $_.CommandLine) }
        throw "Refusing to start workspace while another benchmark process is active."
    }
}

Set-Location -LiteralPath $Root
Set-RunEnvironment
Write-Log "Root=$Root"
Write-Log "ASB root=$AsbRoot"
Write-Log "Workspace root=$WorkspaceRoot"
Write-Log "Workspace ablation root=$WorkspaceAblationRoot"
Write-Log "Ablation root=$AblationRoot"

Wait-AsbProcess
Invoke-CheckedPython @(
    (Join-Path $Root "ICLR\scripts\aggregate_asb_clafr_results.py"),
    "--root",
    $AsbRoot
)

if (-not (Test-AsbComplete)) {
    Write-Log "ASB is not complete; workspace will not start."
    exit 2
}

Assert-NoBenchmarkProcess
Write-Log "ASB complete. Starting AgentDojo workspace selected split."
Invoke-CheckedPython @(
    (Join-Path $Root "ICLR\scripts\run_autodojo_workspace_slice.py"),
    "--out-root",
    $WorkspaceRoot,
    "--split-manifest",
    $WorkspaceManifest
)
Write-Log "Workspace run completed."

Assert-NoBenchmarkProcess
Write-Log "Starting AgentDojo post-generic CLAFR base3 and four-module ablation."
Invoke-CheckedPython @(
    (Join-Path $Root "ICLR\scripts\run_autodojo_table_clafr.py"),
    "--out-root",
    $AblationRoot,
    "--defenses",
    "clafr",
    "clafr_no_evidence_projection",
    "clafr_no_action_evidence_lifting",
    "clafr_no_dynamic_geometry",
    "clafr_no_decision_repair"
)
Write-Log "Four-module ablation completed."

Assert-NoBenchmarkProcess
Write-Log "Starting AgentDojo workspace selected split for CLAFR paper-module ablation."
Invoke-CheckedPython @(
    (Join-Path $Root "ICLR\scripts\run_autodojo_workspace_slice.py"),
    "--out-root",
    $WorkspaceAblationRoot,
    "--split-manifest",
    $WorkspaceManifest,
    "--defenses",
    "clafr",
    "clafr_no_evidence_projection",
    "clafr_no_action_evidence_lifting",
    "clafr_no_dynamic_geometry",
    "clafr_no_decision_repair"
)
Write-Log "Workspace paper-module ablation completed."

Assert-NoBenchmarkProcess
Write-Log "Merging main workspace with paper-module CLAFR base3 row."
Invoke-CheckedPython @(
    (Join-Path $Root "ICLR\scripts\aggregate_autodojo_workspace_full_table.py"),
    "--workspace-root",
    $WorkspaceRoot,
    "--split-manifest",
    $WorkspaceManifest,
    "--base3-clafr-root",
    $AblationRoot,
    "--require-base3-clafr-override"
)
Write-Log "Main workspace merge completed."

Invoke-CheckedPython @(
    (Join-Path $Root "ICLR\scripts\aggregate_autodojo_four_suite_clafr_ablation.py"),
    "--base3-root",
    $AblationRoot,
    "--workspace-root",
    $WorkspaceAblationRoot,
    "--split-manifest",
    $WorkspaceManifest
)
Write-Log "Four-suite paper-module ablation aggregate completed."
