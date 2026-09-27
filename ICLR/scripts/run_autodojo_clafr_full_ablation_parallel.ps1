param(
    [int]$MaxParallel = 8,
    [string]$Manifest = (Join-Path $PSScriptRoot "..\manifests\agentdojo_v122_clafr_full_ablation_4suite.json"),
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\agentdojo_v122_clafr_full_ablation_4suite_20260728")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$AutoDojoRoot = Join-Path $Root "external\official_baselines\AutoDojo"
$Manifest = (Resolve-Path -LiteralPath $Manifest).Path
$OutRoot = [System.IO.Path]::GetFullPath($OutRoot)
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
        [Environment]::SetEnvironmentVariable(
            $parts[0].Trim(),
            $parts[1].Trim().Trim('"').Trim("'"),
            "Process"
        )
    }
}

function Configure-Environment {
    Load-DotEnvNoPrint -Path (Join-Path $Root ".env")
    $env:OPENAI_MODEL = $ModelId
    $env:OPENAI_COMPATIBLE_API_KEY = $env:OPENAI_API_KEY
    $env:OPENAI_COMPATIBLE_BASE_URL = $env:OPENAI_BASE_URL
    $env:SECAGENT_API_KEY = $env:OPENAI_API_KEY
    $env:SECAGENT_BASE_URL = $env:OPENAI_BASE_URL
    $env:AGENTDOJO_OPENAI_TIMEOUT_SECONDS = "120"
    $env:AGENTDOJO_HTTP_RETRIES = "2"
    $env:AGENTDOJO_RUN_INJECTION_UTILITY = "0"
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

Configure-Environment
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutRoot "logs") | Out-Null
Copy-Item -LiteralPath $Manifest -Destination (Join-Path $OutRoot "split_manifest.json") -Force

$manifestData = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$driverLog = Join-Path $OutRoot "logs\parallel_driver.log"
Add-Content -LiteralPath $driverLog -Value ""
Add-Content -LiteralPath $driverLog -Value (
    "===== START {0} max_parallel={1} =====" -f (Get-Date -Format o), $MaxParallel
)

$tasks = [System.Collections.Generic.List[object]]::new()
foreach ($defense in $manifestData.defenses) {
    if ($defense -eq "clafr") {
        Add-Content -LiteralPath $driverLog -Value "SKIP clafr: seeded from completed 71/585 run"
        continue
    }
    foreach ($suiteProperty in $manifestData.suites.PSObject.Properties) {
        $suite = $suiteProperty.Name
        $split = $suiteProperty.Value
        foreach ($group in @("clean", "attack")) {
            $tasks.Add([pscustomobject]@{
                Defense = [string]$defense
                Suite = [string]$suite
                Group = [string]$group
                UserTasks = @($split.user_tasks)
                InjectionTasks = @($split.injection_tasks)
            })
        }
    }
}

$queue = [System.Collections.Queue]::new()
foreach ($task in $tasks) {
    $queue.Enqueue($task)
}
$active = [System.Collections.Generic.List[object]]::new()
$failed = [System.Collections.Generic.List[object]]::new()

function Start-BenchmarkTask {
    param([object]$Task)
    $label = "$($Task.Group)-$($Task.Defense)-$($Task.Suite)"
    $stdout = Join-Path $OutRoot "logs\$label.stdout.log"
    $stderr = Join-Path $OutRoot "logs\$label.stderr.log"
    $args = @(
        "-m", "agentdojo.scripts.benchmark",
        "--model", $ModelId,
        "--model-id", $ModelId,
        "--benchmark-version", $BenchmarkVersion,
        "--suite", $Task.Suite,
        "--defense", $Task.Defense,
        "--logdir", $OutRoot
    )
    if ($Task.Group -eq "attack") {
        $args += @("--attack", $AttackName)
    }
    foreach ($userTask in $Task.UserTasks) {
        $args += @("--user-task", [string]$userTask)
    }
    if ($Task.Group -eq "attack") {
        foreach ($injectionTask in $Task.InjectionTasks) {
            $args += @("--injection-task", [string]$injectionTask)
        }
    }
    $process = Start-Process `
        -FilePath "python" `
        -ArgumentList $args `
        -WorkingDirectory $AutoDojoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    Add-Content -LiteralPath $driverLog -Value (
        "START pid={0} label={1} {2}" -f $process.Id, $label, (Get-Date -Format o)
    )
    return [pscustomobject]@{
        Label = $label
        Process = $process
        Stdout = $stdout
        Stderr = $stderr
    }
}

while ($queue.Count -gt 0 -or $active.Count -gt 0) {
    while ($queue.Count -gt 0 -and $active.Count -lt $MaxParallel) {
        $active.Add((Start-BenchmarkTask -Task $queue.Dequeue()))
    }
    Start-Sleep -Seconds 5
    for ($index = $active.Count - 1; $index -ge 0; $index--) {
        $item = $active[$index]
        if (-not $item.Process.HasExited) {
            continue
        }
        $item.Process.Refresh()
        $exitCode = [int]$item.Process.ExitCode
        Add-Content -LiteralPath $driverLog -Value (
            "END exit={0} label={1} {2}" -f $exitCode, $item.Label, (Get-Date -Format o)
        )
        if ($exitCode -ne 0) {
            $failed.Add($item)
        }
        $active.RemoveAt($index)
    }
}

python ICLR\scripts\aggregate_autodojo_clafr_manifest.py `
    --root $OutRoot `
    --manifest $Manifest
$aggregateExit = $LASTEXITCODE
Add-Content -LiteralPath $driverLog -Value (
    "===== END {0} failed={1} aggregate_exit={2} =====" -f
    (Get-Date -Format o), $failed.Count, $aggregateExit
)
if ($failed.Count -gt 0 -or $aggregateExit -ne 0) {
    foreach ($item in $failed) {
        Add-Content -LiteralPath $driverLog -Value (
            "FAILED label={0} stdout={1} stderr={2}" -f
            $item.Label, $item.Stdout, $item.Stderr
        )
    }
    exit 1
}
