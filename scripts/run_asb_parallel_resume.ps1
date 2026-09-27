param(
    [string]$Root = "",
    [string]$OutRoot = "",
    [string[]]$Variants = @("ts_guard_style", "ts_flow_style", "clafr_full", "clafr_feedback"),
    [int]$MaxCases = 200,
    [int]$TaskNums = 5,
    [int]$AttackLimit = 4,
    [int]$MaxTurns = 8,
    [int]$TimeoutSeconds = 120,
    [int]$Retries = 2
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if ([string]::IsNullOrWhiteSpace($OutRoot)) {
    $OutRoot = Join-Path $Root "results\runs\asb_200_rr_source_trust_strong_baselines_deepseek_v1"
}

$FullVariants = @(
    "baseline",
    "prompt_policy",
    "ts_guard_style",
    "ts_flow_style",
    "clafr_full",
    "clafr_feedback"
)
$LogDir = Join-Path $OutRoot "parallel_logs"
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Set-RunEnvironment {
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:NO_COLOR = "1"
    $env:TERM = "dumb"
    $env:PYTHONPATH = (
        (Join-Path $Root "src") + ";" +
        (Join-Path $Root "src") + ";" +
        $Root
    )
}

function Invoke-AsbManifest {
    param([string[]]$ManifestVariants)
    & python "scripts\run_asb_clafr_agent_score.py" `
        --output-dir $OutRoot `
        --model-id deepseek-v4-flash `
        --task-nums $TaskNums `
        --attack-limit $AttackLimit `
        --attack-sampling stratified `
        --case-sampling agent_round_robin `
        --max-cases $MaxCases `
        --max-turns $MaxTurns `
        --timeout-seconds $TimeoutSeconds `
        --retries $Retries `
        --tool-provenance source_trust `
        --variants $ManifestVariants `
        --manifest-only
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to write ASB manifest."
    }
}

Set-Location -LiteralPath $Root
Set-RunEnvironment

Invoke-AsbManifest -ManifestVariants $FullVariants

$workers = @()
foreach ($variant in $Variants) {
    $stdout = Join-Path $LogDir ("{0}.stdout.log" -f $variant)
    $stderr = Join-Path $LogDir ("{0}.stderr.log" -f $variant)
    $command = @"
Set-Location -LiteralPath '$Root'
`$env:PYTHONUTF8='1'
`$env:PYTHONIOENCODING='utf-8'
`$env:NO_COLOR='1'
`$env:TERM='dumb'
`$env:PYTHONPATH='$((Join-Path $Root "src"));$((Join-Path $Root "src"));$Root'
python scripts\run_asb_clafr_agent_score.py --output-dir '$OutRoot' --model-id deepseek-v4-flash --task-nums $TaskNums --attack-limit $AttackLimit --attack-sampling stratified --case-sampling agent_round_robin --max-cases $MaxCases --max-turns $MaxTurns --timeout-seconds $TimeoutSeconds --retries $Retries --tool-provenance source_trust --variants $variant
"@
    $process = Start-Process -FilePath "powershell" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command) `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru
    $workers += [pscustomobject]@{
        Variant = $variant
        Process = $process
        Stdout = $stdout
        Stderr = $stderr
    }
}

$failed = @()
foreach ($worker in $workers) {
    Wait-Process -Id $worker.Process.Id
    $process = Get-Process -Id $worker.Process.Id -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        $process.Refresh()
    }
    $exitCode = $worker.Process.ExitCode
    if ($exitCode -ne 0) {
        $failed += [pscustomobject]@{
            Variant = $worker.Variant
            ExitCode = $exitCode
            Stdout = $worker.Stdout
            Stderr = $worker.Stderr
        }
    }
}

Invoke-AsbManifest -ManifestVariants $FullVariants

if ($failed.Count -gt 0) {
    $failed | ConvertTo-Json -Depth 3 | Write-Error
    exit 1
}

exit 0
