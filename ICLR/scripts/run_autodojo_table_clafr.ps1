param(
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\autodojo_table_clafr_full"),
    [string[]]$Suites = @("banking", "slack", "travel"),
    [string[]]$Defenses = @("clafr"),
    [switch]$CleanOnly,
    [switch]$AttackOnly,
    [switch]$ForceRerun
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $Root
$AutoDojoRoot = Join-Path $Root "external\official_baselines\AutoDojo"
$ModelId = "deepseek-v4-flash"
$BenchmarkVersion = "v1.2.2"
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
    [Environment]::SetEnvironmentVariable("AGENTDOJO_RUN_INJECTION_UTILITY", "0", "Process")
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "Process")
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "Process")
    [Environment]::SetEnvironmentVariable("NO_COLOR", "1", "Process")
    [Environment]::SetEnvironmentVariable("TERM", "dumb", "Process")
    [Environment]::SetEnvironmentVariable("PYTHONPATH", "agentdojo/src;agentdojo/variant_generation", "Process")
}

function Invoke-Benchmark {
    param(
        [string]$Defense,
        [string]$Suite,
        [bool]$WithAttack
    )
    $group = if ($WithAttack) { "attack" } else { "clean" }
    $log = Join-Path $OutRoot "logs\$group-$Defense-$Suite.log"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
    $args = @(
        "-m", "agentdojo.scripts.benchmark",
        "--model", $ModelId,
        "--model-id", $ModelId,
        "--benchmark-version", $BenchmarkVersion,
        "--suite", $Suite,
        "--defense", $Defense,
        "--logdir", $OutRoot
    )
    if ($WithAttack) {
        $args += @("--attack", $AttackName)
    }
    if ($ForceRerun) {
        $args += @("--force-rerun")
    }
    Add-Content -LiteralPath $log -Value "===== START $group $Defense $Suite $(Get-Date -Format o) ====="
    Add-Content -LiteralPath $log -Value "python $($args -join ' ')"
    $stdoutPath = "$log.stdout.tmp"
    $stderrPath = "$log.stderr.tmp"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    $process = Start-Process `
        -FilePath "python" `
        -ArgumentList $args `
        -WorkingDirectory $AutoDojoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -Wait `
        -PassThru
    if (Test-Path -LiteralPath $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath | Add-Content -LiteralPath $log
    }
    if (Test-Path -LiteralPath $stderrPath) {
        Get-Content -LiteralPath $stderrPath | Add-Content -LiteralPath $log
    }
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    Add-Content -LiteralPath $log -Value "===== END $group $Defense $Suite exit=$($process.ExitCode) $(Get-Date -Format o) ====="
    if ($process.ExitCode -ne 0) {
        throw "$group $Defense $Suite failed with exit code $($process.ExitCode); see $log"
    }
}

Configure-DeepSeekRoute
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

foreach ($defense in $Defenses) {
    if (-not $AttackOnly) {
        foreach ($suite in $Suites) {
            Invoke-Benchmark -Defense $defense -Suite $suite -WithAttack $false
        }
    }
    if (-not $CleanOnly) {
        foreach ($suite in $Suites) {
            Invoke-Benchmark -Defense $defense -Suite $suite -WithAttack $true
        }
    }
}

python (Join-Path $Root "ICLR\scripts\aggregate_autodojo_table.py") --root $OutRoot --model-id $ModelId --benchmark-version $BenchmarkVersion
