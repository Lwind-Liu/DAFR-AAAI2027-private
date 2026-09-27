param(
    [string]$Root = "",
    [string]$Base3Root = "",
    [string]$WorkspaceRoot = "",
    [string]$SplitManifest = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
if ([string]::IsNullOrWhiteSpace($Base3Root)) {
    $Base3Root = Join-Path $Root "ICLR\results\autodojo_table_clafr_paper_ablation_1third_v1"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $Root "ICLR\results\autodojo_v122_workspace_5x14_clafr_paper_ablation_1third_v1"
}
if ([string]::IsNullOrWhiteSpace($SplitManifest)) {
    $SplitManifest = Join-Path $WorkspaceRoot "split_manifest.json"
}

$LogDir = Join-Path $Root "ICLR\results\pipeline_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("autodojo_clafr_paper_ablation_1third_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Output $line
}

function Invoke-CheckedPython {
    param([string[]]$Arguments)
    Write-Log ("python " + ($Arguments -join " "))
    & python @Arguments 2>&1 | Tee-Object -FilePath $LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
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

function Assert-NoBenchmarkProcess {
    $currentPid = $PID
    $active = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $currentPid -and
        $_.CommandLine -match "run_autodojo_workspace_slice|agentdojo\.scripts\.benchmark|run_autodojo_table_clafr"
    }
    if ($active) {
        $active | ForEach-Object { Write-Log ("Still active: PID {0} {1}" -f $_.ProcessId, $_.CommandLine) }
        throw "Refusing to start while another AutoDojo benchmark process is active."
    }
}

Set-Location -LiteralPath $Root
Set-RunEnvironment

$Defenses = @(
    "clafr",
    "clafr_no_evidence_projection",
    "clafr_no_action_evidence_lifting",
    "clafr_no_dynamic_geometry",
    "clafr_no_decision_repair"
)

Write-Log "Root=$Root"
Write-Log "Base3 root=$Base3Root"
Write-Log "Workspace root=$WorkspaceRoot"
Write-Log "Split manifest=$SplitManifest"

Assert-NoBenchmarkProcess

$BankingArgs = @(
    (Join-Path $Root "ICLR\scripts\run_autodojo_table_clafr.py"),
    "--out-root", $Base3Root,
    "--suites", "banking",
    "--defenses"
) + $Defenses + @(
    "--user-tasks", "user_task_0", "user_task_1", "user_task_2", "user_task_4", "user_task_8", "user_task_9",
    "--injection-tasks", "injection_task_0", "injection_task_1", "injection_task_2", "injection_task_3", "injection_task_4", "injection_task_5", "injection_task_6", "injection_task_7", "injection_task_8"
)
Invoke-CheckedPython $BankingArgs

$SlackArgs = @(
    (Join-Path $Root "ICLR\scripts\run_autodojo_table_clafr.py"),
    "--out-root", $Base3Root,
    "--suites", "slack",
    "--defenses"
) + $Defenses + @(
    "--user-tasks", "user_task_3", "user_task_5", "user_task_7", "user_task_10", "user_task_12", "user_task_16", "user_task_17",
    "--injection-tasks", "injection_task_1", "injection_task_2", "injection_task_3", "injection_task_4", "injection_task_5"
)
Invoke-CheckedPython $SlackArgs

$TravelArgs = @(
    (Join-Path $Root "ICLR\scripts\run_autodojo_table_clafr.py"),
    "--out-root", $Base3Root,
    "--suites", "travel",
    "--defenses"
) + $Defenses + @(
    "--user-tasks", "user_task_2", "user_task_6", "user_task_8", "user_task_9", "user_task_16", "user_task_18", "user_task_19",
    "--injection-tasks", "injection_task_0", "injection_task_1", "injection_task_2", "injection_task_3", "injection_task_4", "injection_task_5", "injection_task_6"
)
Invoke-CheckedPython $TravelArgs

$WorkspaceArgs = @(
    (Join-Path $Root "ICLR\scripts\run_autodojo_workspace_slice.py"),
    "--out-root", $WorkspaceRoot,
    "--split-manifest", $SplitManifest,
    "--defenses"
) + $Defenses
Invoke-CheckedPython $WorkspaceArgs

Invoke-CheckedPython @(
    (Join-Path $Root "ICLR\scripts\aggregate_autodojo_four_suite_clafr_ablation.py"),
    "--base3-root", $Base3Root,
    "--workspace-root", $WorkspaceRoot,
    "--split-manifest", $SplitManifest
)

Write-Log "Done. Final table: $(Join-Path $WorkspaceRoot 'autodojo_v122_4suite_clafr_ablation.md')"
