param(
    [switch]$Smoke,
    [switch]$ForceRerun,
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\deepseek64_clafr_official"),
    [string[]]$Suites = @("workspace", "travel", "banking", "slack")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $Root
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
    [Environment]::SetEnvironmentVariable("AGENTDOJO_OPENAI_TIMEOUT_SECONDS", "120", "Process")
    [Environment]::SetEnvironmentVariable("AGENTDOJO_HTTP_RETRIES", "2", "Process")
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
    $argList = New-Object System.Collections.Generic.List[string]
    for ($idx = 0; $idx -lt $PythonArgs.Count; $idx++) {
        if ($null -eq $PythonArgs[$idx]) {
            Add-Content -LiteralPath $LogPath -Value "NULL_ARGUMENT_INDEX: $idx"
            throw "$Label has a null command argument at index $idx"
        }
        $argList.Add([string]$PythonArgs[$idx])
    }
    $stdoutPath = "$LogPath.stdout.tmp"
    $stderrPath = "$LogPath.stderr.tmp"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    try {
        $process = Start-Process `
            -FilePath "python" `
            -ArgumentList $argList.ToArray() `
            -WorkingDirectory $Root `
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

function Run-AgentDojoSuite {
    param(
        [string]$Suite,
        [string[]]$Users,
        [string[]]$Injections,
        [string]$RunGroup
    )
    $outDir = Join-Path $OutRoot "$RunGroup\$Suite"
    $log = Join-Path $OutRoot "logs\$RunGroup-$Suite.log"
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
        "--max-tool-iters", "15",
        "--fail-on-provider-error",
        "--http-llm"
    )
    if ($ForceRerun) {
        $args += @("--force-rerun")
    }
    Invoke-PythonStep -Label "$RunGroup $Suite" -PythonArgs $args -LogPath $log
}

Configure-DeepSeekRoute
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

if ($Smoke) {
    $spec = $Split["workspace"]
    Run-AgentDojoSuite -Suite "workspace" -Users @($spec["users"][0]) -Injections @($spec["injections"][0]) -RunGroup "smoke"
}
else {
    foreach ($suite in $Suites) {
        if (-not $Split.Contains($suite)) {
            throw "Unknown suite: $suite"
        }
        $spec = $Split[$suite]
        Run-AgentDojoSuite -Suite $suite -Users ([string[]]$spec["users"]) -Injections ([string[]]$spec["injections"]) -RunGroup "official64"
    }
    python ICLR\scripts\aggregate_deepseek64_clafr_official.py --root $OutRoot --group official64
}
