param(
    [switch]$ForceRerun,
    [string]$AutoDojoRoot = (Join-Path $PSScriptRoot "..\external\official_baselines\AutoDojo"),
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\runs\autodojo_deepseek_reference_baselines"),
    [string[]]$Suites = @("banking", "slack", "travel"),
    [string[]]$Defenses = @("no_defense", "reminder", "datafilter", "progent", "drift"),
    [ValidateSet("clean", "static", "autodojo")]
    [string[]]$Modes = @("clean", "static", "autodojo")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root
$Model = "deepseek/deepseek-v4-flash"
$ModelCachePath = "deepseek\deepseek-v4-flash"

function Load-DotEnvNoPrint {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim().Trim('"').Trim("'"), "Process")
    }
}

function Assert-AutoDojoReady {
    if (-not (Test-Path -LiteralPath $AutoDojoRoot)) {
        throw "Missing AutoDojo root: $AutoDojoRoot"
    }
    if (-not $env:OPENROUTER_API_KEY) {
        throw "AutoDojo's official non-local model route requires OPENROUTER_API_KEY. Current .env only supports direct OpenAI-compatible DeepSeek routing; do not call this a reproduced AutoDojo baseline until OpenRouter or an explicitly documented route patch is configured."
    }
}

function DefenseArgs {
    param([string]$Defense, [string]$Suite)
    if ($Defense -eq "no_defense") {
        return @()
    }
    $args = @("--defense", $Defense)
    if ($Defense -eq "drift") {
        $args += @(
            "--defense-model", "openai/gpt-4o",
            "--drift-cache-dir", "agentdojo\variant_generation\drift\cache",
            "--drift-cache-label", "openai/gpt-4o"
        )
    }
    elseif ($Defense -eq "progent") {
        $args += @(
            "--defense-model", "openai/gpt-4o",
            "--progent-cache-dir", "agentdojo\variant_generation\progent\cache",
            "--progent-cache-label", "openai/gpt-4o"
        )
    }
    return $args
}

function Invoke-PythonStep {
    param(
        [string]$Label,
        [string[]]$PythonArgs,
        [string]$LogPath
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null
    Add-Content -LiteralPath $LogPath -Value ""
    Add-Content -LiteralPath $LogPath -Value "===== START $Label $(Get-Date -Format o) ====="
    $stdoutPath = "$LogPath.stdout.tmp"
    $stderrPath = "$LogPath.stderr.tmp"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    try {
        $env:PYTHONPATH = "agentdojo\src;agentdojo\variant_generation"
        $process = Start-Process `
            -FilePath "python" `
            -ArgumentList $PythonArgs `
            -WorkingDirectory $AutoDojoRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -Wait `
            -PassThru
        $exitCode = $process.ExitCode
        if (Test-Path -LiteralPath $stdoutPath) {
            Get-Content -LiteralPath $stdoutPath | Add-Content -LiteralPath $LogPath
        }
        if (Test-Path -LiteralPath $stderrPath) {
            Get-Content -LiteralPath $stderrPath | Add-Content -LiteralPath $LogPath
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
    Add-Content -LiteralPath $LogPath -Value "===== END $Label exit=$exitCode $(Get-Date -Format o) ====="
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode; see $LogPath"
    }
}

function Run-Benchmark {
    param(
        [string]$Suite,
        [string]$Defense,
        [string]$Mode
    )
    $runLog = Join-Path $OutRoot "logs\$Mode-$Defense-$Suite.log"
    $args = @(
        "-m", "agentdojo.scripts.benchmark",
        "--model", $Model,
        "--suite", $Suite,
        "--benchmark-version", "v1.2.2",
        "--logdir", $OutRoot
    ) + (DefenseArgs -Defense $Defense -Suite $Suite)
    if ($Mode -eq "static") {
        $args += @("--attack", "important_instructions")
    }
    elseif ($Mode -eq "autodojo") {
        $cache = Join-Path $AutoDojoRoot "agentdojo\variant_generation\variants\$Suite\$ModelCachePath\$Defense\injections.json"
        if (-not (Test-Path -LiteralPath $cache)) {
            throw "Missing AutoDojo injection cache: $cache"
        }
        [Environment]::SetEnvironmentVariable("AUTODOJO_CACHE", $cache, "Process")
        [Environment]::SetEnvironmentVariable("AUTODOJO_VARIANT", "0", "Process")
        $args += @("--attack", "autodojo", "--injection-attack-name", "autodojo")
    }
    if ($ForceRerun) {
        $args += @("--force-rerun")
    }
    Invoke-PythonStep -Label "$Mode $Defense $Suite" -PythonArgs $args -LogPath $runLog
}

function Run-Aggregate {
    param(
        [string]$Defense,
        [string]$Mode
    )
    $attack = if ($Mode -eq "clean") { "none" } elseif ($Mode -eq "static") { "important_instructions" } else { "autodojo" }
    $pipeline = "$Model/$Defense"
    $log = Join-Path $OutRoot "logs\aggregate-$Mode-$Defense.log"
    $args = @(
        "agentdojo\variant_generation\aggregate_results.py",
        "--pipeline", $pipeline,
        "--attack", $attack,
        "--logdir", $OutRoot,
        "--benchmark-version", "v1.2.2",
        "--table"
    )
    foreach ($suite in $Suites) {
        $args += @("-s", $suite)
    }
    Invoke-PythonStep -Label "aggregate $Mode $Defense" -PythonArgs $args -LogPath $log
}

Load-DotEnvNoPrint -Path (Join-Path (Split-Path -Parent (Split-Path -Parent $AutoDojoRoot)) ".env")
Load-DotEnvNoPrint -Path (Join-Path $AutoDojoRoot ".env")
Assert-AutoDojoReady
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

foreach ($mode in $Modes) {
    foreach ($defense in $Defenses) {
        foreach ($suite in $Suites) {
            Run-Benchmark -Suite $suite -Defense $defense -Mode $mode
        }
        Run-Aggregate -Defense $defense -Mode $mode
    }
}
