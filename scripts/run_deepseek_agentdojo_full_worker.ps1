param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("clean", "attack")]
    [string]$Group,
    [Parameter(Mandatory=$true)]
    [ValidateSet("runner", "autodojo")]
    [string]$Source,
    [Parameter(Mandatory=$true)]
    [string]$Suite,
    [Parameter(Mandatory=$true)]
    [string]$Method,
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\runs\deepseek_agentdojo_full_629_97"),
    [string]$BenchmarkVersion = "v1",
    [switch]$ForceRerun
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root
$AutoDojoRoot = Join-Path $Root "external\official_baselines\AutoDojo"
$ModelId = "deepseek-v4-flash"
$AttackName = "important_instructions"

function Load-DotEnvNoPrint {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing dotenv file: $Path"
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

function Configure-DeepSeekRoute {
    Load-DotEnvNoPrint -Path (Join-Path $Root ".env")
    [Environment]::SetEnvironmentVariable("OPENAI_MODEL", $ModelId, "Process")
    [Environment]::SetEnvironmentVariable("OPENAI_COMPATIBLE_API_KEY", $env:OPENAI_API_KEY, "Process")
    [Environment]::SetEnvironmentVariable("OPENAI_COMPATIBLE_BASE_URL", $env:OPENAI_BASE_URL, "Process")
    [Environment]::SetEnvironmentVariable("SECAGENT_API_KEY", $env:OPENAI_API_KEY, "Process")
    [Environment]::SetEnvironmentVariable("SECAGENT_BASE_URL", $env:OPENAI_BASE_URL, "Process")
    [Environment]::SetEnvironmentVariable("AGENTDOJO_OPENAI_TIMEOUT_SECONDS", "120", "Process")
    [Environment]::SetEnvironmentVariable("AGENTDOJO_HTTP_RETRIES", "2", "Process")
    [Environment]::SetEnvironmentVariable("AGENTDOJO_RUN_INJECTION_UTILITY", "0", "Process")
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "Process")
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "Process")
    [Environment]::SetEnvironmentVariable("NO_COLOR", "1", "Process")
    [Environment]::SetEnvironmentVariable("TERM", "dumb", "Process")
}

function Invoke-PythonStep {
    param(
        [string]$Label,
        [string]$WorkDir,
        [string[]]$PythonArgs,
        [string]$LogPath,
        [string]$PythonPath = ""
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null
    Add-Content -LiteralPath $LogPath -Value ""
    Add-Content -LiteralPath $LogPath -Value "===== START $Label $(Get-Date -Format o) ====="
    Add-Content -LiteralPath $LogPath -Value "python $($PythonArgs -join ' ')"
    $stdoutPath = "$LogPath.stdout.tmp"
    $stderrPath = "$LogPath.stderr.tmp"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    $oldPythonPath = $env:PYTHONPATH
    try {
        if ($PythonPath) {
            [Environment]::SetEnvironmentVariable("PYTHONPATH", $PythonPath, "Process")
        }
        $process = Start-Process `
            -FilePath "python" `
            -ArgumentList $PythonArgs `
            -WorkingDirectory $WorkDir `
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
        [Environment]::SetEnvironmentVariable("PYTHONPATH", $oldPythonPath, "Process")
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
    Add-Content -LiteralPath $LogPath -Value "===== END $Label exit=$exitCode $(Get-Date -Format o) ====="
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode; see $LogPath"
    }
}

Configure-DeepSeekRoute
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

$withAttack = $Group -eq "attack"
$safeMethod = $Method -replace '[^a-zA-Z0-9_.-]', '_'
$log = Join-Path $OutRoot "logs\worker-$Group-$Source-$safeMethod-$Suite.log"

if ($Source -eq "runner") {
    $outDir = Join-Path $OutRoot "runner_$Group\$Suite`__$safeMethod"
    $args = @(
        "scripts\run_agentdojo_full_agent_score.py",
        "--suite", $Suite
    )
    if ($withAttack) {
        $args += @("--attack", $AttackName)
    }
    $args += @(
        "--benchmark-version", $BenchmarkVersion,
        "--model-id", $ModelId,
        "--variants", $Method,
        "--output-dir", $outDir,
        "--openai-timeout-seconds", "120",
        "--judge-timeout-seconds", "120",
        "--max-tool-iters", "15",
        "--fail-on-provider-error",
        "--http-llm"
    )
    if ($ForceRerun) {
        $args += @("--force-rerun")
    }
    Invoke-PythonStep -Label "$Group runner $Method $Suite" -WorkDir $Root -PythonArgs $args -LogPath $log
}
else {
    $logDir = Join-Path $OutRoot "autodojo_$Group"
    $args = @(
        "-m", "agentdojo.scripts.benchmark",
        "--suite", $Suite,
        "--model", $ModelId,
        "--model-id", $ModelId,
        "--benchmark-version", $BenchmarkVersion,
        "--defense", $Method,
        "--defense-model", $ModelId,
        "--defense-model-id", $ModelId,
        "--logdir", $logDir
    )
    if ($withAttack) {
        $args += @("--attack", $AttackName)
    }
    if ($ForceRerun) {
        $args += @("--force-rerun")
    }
    Invoke-PythonStep `
        -Label "$Group autodojo $Method $Suite" `
        -WorkDir $AutoDojoRoot `
        -PythonArgs $args `
        -LogPath $log `
        -PythonPath "agentdojo\src;agentdojo\variant_generation"
}

python scripts\aggregate_agentdojo_full_629_97.py --root $OutRoot --model-id $ModelId --benchmark-version $BenchmarkVersion
