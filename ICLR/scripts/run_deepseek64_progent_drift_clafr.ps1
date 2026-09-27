param(
    [switch]$Smoke,
    [switch]$ForceRerun,
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\deepseek64_progent_drift_clafr"),
    [string[]]$Suites = @("workspace", "travel", "banking", "slack")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $Root
$AutoDojoRoot = Join-Path $Root "external\official_baselines\AutoDojo"
$ModelId = "deepseek-v4-flash"

$Split = [ordered]@{
    workspace = @{
        users = @("user_task_29", "user_task_21", "user_task_39", "user_task_6")
        injections = @("injection_task_1", "injection_task_5", "injection_task_4", "injection_task_3")
    }
    travel = @{
        users = @("user_task_10", "user_task_7", "user_task_8", "user_task_17")
        injections = @("injection_task_0", "injection_task_5", "injection_task_1", "injection_task_6")
    }
    banking = @{
        users = @("user_task_4", "user_task_13", "user_task_8", "user_task_9")
        injections = @("injection_task_8", "injection_task_3", "injection_task_1", "injection_task_0")
    }
    slack = @{
        users = @("user_task_14", "user_task_13", "user_task_10", "user_task_3")
        injections = @("injection_task_1", "injection_task_2", "injection_task_3", "injection_task_4")
    }
}

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

function Run-CLAFR {
    param(
        [string]$Suite,
        [string[]]$Users,
        [string[]]$Injections,
        [string]$RunGroup
    )
    $outDir = Join-Path $OutRoot "clafr\$RunGroup\$Suite"
    $log = Join-Path $OutRoot "logs\$RunGroup-clafr-$Suite.log"
    $args = @(
        "scripts\run_agentdojo_full_agent_score.py",
        "--suite", $Suite,
        "--user-tasks"
    ) + $Users + @(
        "--injection-tasks"
    ) + $Injections + @(
        "--attack", "important_instructions",
        "--benchmark-version", "v1.2.2",
        "--model-id", $ModelId,
        "--variants", "clafr_full",
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
    Invoke-PythonStep -Label "$RunGroup CLAFR $Suite" -WorkDir $Root -PythonArgs $args -LogPath $log
}

function Run-AutoDojoDefense {
    param(
        [string]$Defense,
        [string]$Suite,
        [string[]]$Users,
        [string[]]$Injections,
        [string]$RunGroup
    )
    $logDir = Join-Path $OutRoot "autodojo\$RunGroup"
    $log = Join-Path $OutRoot "logs\$RunGroup-$Defense-$Suite.log"
    $args = @(
        "-m", "agentdojo.scripts.benchmark",
        "--suite", $Suite,
        "--model", $ModelId,
        "--model-id", $ModelId,
        "--benchmark-version", "v1.2.2",
        "--attack", "important_instructions",
        "--defense", $Defense,
        "--defense-model", $ModelId,
        "--defense-model-id", $ModelId,
        "--logdir", $logDir
    )
    foreach ($user in $Users) {
        $args += @("--user-task", $user)
    }
    foreach ($injection in $Injections) {
        $args += @("--injection-task", $injection)
    }
    if ($ForceRerun) {
        $args += @("--force-rerun")
    }
    Invoke-PythonStep `
        -Label "$RunGroup $Defense $Suite" `
        -WorkDir $AutoDojoRoot `
        -PythonArgs $args `
        -LogPath $log `
        -PythonPath "agentdojo\src;agentdojo\variant_generation"
}

function Run-Group {
    param([string]$RunGroup)
    foreach ($suite in $Suites) {
        if (-not $Split.Contains($suite)) {
            throw "Unknown suite: $suite"
        }
        $spec = $Split[$suite]
        $users = [string[]]$spec["users"]
        $injections = [string[]]$spec["injections"]
        if ($RunGroup -eq "smoke") {
            $users = @($users[0])
            $injections = @($injections[0])
        }
        Run-CLAFR -Suite $suite -Users $users -Injections $injections -RunGroup $RunGroup
        Run-AutoDojoDefense -Defense "progent" -Suite $suite -Users $users -Injections $injections -RunGroup $RunGroup
        Run-AutoDojoDefense -Defense "drift" -Suite $suite -Users $users -Injections $injections -RunGroup $RunGroup
        if ($RunGroup -eq "smoke") {
            break
        }
    }
    python ICLR\scripts\aggregate_progent_drift_clafr64.py --root $OutRoot --group $RunGroup
}

Configure-DeepSeekRoute
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

if ($Smoke) {
    Run-Group -RunGroup "smoke"
}
else {
    Run-Group -RunGroup "official64"
}
