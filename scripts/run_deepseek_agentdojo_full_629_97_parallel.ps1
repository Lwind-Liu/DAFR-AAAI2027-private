param(
    [int]$MaxParallel = 4,
    [switch]$AttackOnly,
    [switch]$CleanOnly,
    [switch]$ForceRerun,
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\runs\deepseek_agentdojo_full_629_97"),
    [string]$BenchmarkVersion = "v1",
    [string[]]$Suites = @("workspace", "travel", "banking", "slack"),
    [string[]]$RunnerVariants = @("clafr_full", "agentdojo_tool_filter", "agentdojo_spotlighting", "agentdojo_repeat_user_prompt"),
    [string[]]$AutoDojoDefenses = @("progent", "drift")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $Root
$Worker = Join-Path $Root "scripts\run_deepseek_agentdojo_full_worker.ps1"
$ModelId = "deepseek-v4-flash"
$groups = @()
if (-not $AttackOnly) { $groups += "clean" }
if (-not $CleanOnly) { $groups += "attack" }
$ExpectedCleanBySuite = @{
    workspace = 40
    travel = 20
    banking = 16
    slack = 21
}
$ExpectedAttackBySuite = @{
    workspace = 240
    travel = 140
    banking = 144
    slack = 105
}

New-Item -ItemType Directory -Force -Path (Join-Path $OutRoot "logs") | Out-Null
$driverLog = Join-Path $OutRoot "logs\parallel_driver.log"
Add-Content -LiteralPath $driverLog -Value ""
Add-Content -LiteralPath $driverLog -Value "===== PARALLEL START $(Get-Date -Format o) max=$MaxParallel benchmark=$BenchmarkVersion ====="

python scripts\aggregate_agentdojo_full_629_97.py --root $OutRoot --model-id $ModelId --benchmark-version $BenchmarkVersion | Out-Null
$caseRowsPath = Join-Path $OutRoot "full_case_rows.csv"
$existingRows = @()
if (Test-Path -LiteralPath $caseRowsPath) {
    $existingRows = Import-Csv -LiteralPath $caseRowsPath
}

function Get-ExistingCount {
    param(
        [string]$Group,
        [string]$Method,
        [string]$Suite
    )
    return @($existingRows | Where-Object {
        $_.group -eq $Group -and $_.method_key -eq $Method -and $_.suite -eq $Suite
    }).Count
}

function Get-ExpectedCount {
    param(
        [string]$Group,
        [string]$Suite
    )
    if ($Group -eq "clean" -and $ExpectedCleanBySuite.ContainsKey($Suite)) {
        return [int]$ExpectedCleanBySuite[$Suite]
    }
    if ($Group -eq "attack" -and $ExpectedAttackBySuite.ContainsKey($Suite)) {
        return [int]$ExpectedAttackBySuite[$Suite]
    }
    return 0
}

$tasks = New-Object System.Collections.Generic.List[object]
foreach ($group in $groups) {
    foreach ($suite in $Suites) {
        foreach ($variant in $RunnerVariants) {
            $expected = Get-ExpectedCount -Group $group -Suite $suite
            if ($expected -gt 0) {
                $existing = Get-ExistingCount -Group $group -Method $variant -Suite $suite
                if ($existing -ge $expected) {
                    Add-Content -LiteralPath $driverLog -Value "SKIP complete group=$group source=runner method=$variant suite=$suite cases=$existing"
                    continue
                }
            }
            $tasks.Add([pscustomobject]@{
                Group = $group
                Source = "runner"
                Suite = $suite
                Method = $variant
            })
        }
        foreach ($defense in $AutoDojoDefenses) {
            $expected = Get-ExpectedCount -Group $group -Suite $suite
            if ($expected -gt 0) {
                $existing = Get-ExistingCount -Group $group -Method $defense -Suite $suite
                if ($existing -ge $expected) {
                    Add-Content -LiteralPath $driverLog -Value "SKIP complete group=$group source=autodojo method=$defense suite=$suite cases=$existing"
                    continue
                }
            }
            $tasks.Add([pscustomobject]@{
                Group = $group
                Source = "autodojo"
                Suite = $suite
                Method = $defense
            })
        }
    }
}

$queue = New-Object System.Collections.Queue
foreach ($task in $tasks) { $queue.Enqueue($task) }
$active = New-Object System.Collections.Generic.List[object]
$failed = New-Object System.Collections.Generic.List[object]

function Start-TaskProcess {
    param([object]$Task)
    $safeMethod = $Task.Method -replace '[^a-zA-Z0-9_.-]', '_'
    $label = "$($Task.Group)-$($Task.Source)-$safeMethod-$($Task.Suite)"
    $stdout = Join-Path $OutRoot "logs\launcher-$label.stdout.log"
    $stderr = Join-Path $OutRoot "logs\launcher-$label.stderr.log"
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $Worker,
        "-Group", $Task.Group,
        "-Source", $Task.Source,
        "-Suite", $Task.Suite,
        "-Method", $Task.Method,
        "-OutRoot", $OutRoot,
        "-BenchmarkVersion", $BenchmarkVersion
    )
    if ($ForceRerun) {
        $args += "-ForceRerun"
    }
    $process = Start-Process `
        -FilePath "powershell" `
        -ArgumentList $args `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    Add-Content -LiteralPath $driverLog -Value "START pid=$($process.Id) label=$label $(Get-Date -Format o)"
    return [pscustomobject]@{
        Label = $label
        Process = $process
        Stdout = $stdout
        Stderr = $stderr
    }
}

while ($queue.Count -gt 0 -or $active.Count -gt 0) {
    while ($queue.Count -gt 0 -and $active.Count -lt $MaxParallel) {
        $active.Add((Start-TaskProcess -Task $queue.Dequeue()))
    }

    Start-Sleep -Seconds 10

    for ($idx = $active.Count - 1; $idx -ge 0; $idx--) {
        $item = $active[$idx]
        $proc = Get-Process -Id $item.Process.Id -ErrorAction SilentlyContinue
        if ($null -ne $proc -and -not $proc.HasExited) {
            continue
        }
        try {
            $item.Process.WaitForExit(1000) | Out-Null
            $item.Process.Refresh()
            $exitCode = [int]$item.Process.ExitCode
        }
        catch {
            $exitCode = -999
        }
        Add-Content -LiteralPath $driverLog -Value "END exit=$exitCode label=$($item.Label) $(Get-Date -Format o)"
        if ($exitCode -ne 0) {
            $failed.Add($item)
        }
        $active.RemoveAt($idx)
        python scripts\aggregate_agentdojo_full_629_97.py --root $OutRoot --model-id $ModelId --benchmark-version $BenchmarkVersion | Out-Null
    }
}

python scripts\aggregate_agentdojo_full_629_97.py --root $OutRoot --model-id $ModelId --benchmark-version $BenchmarkVersion
Add-Content -LiteralPath $driverLog -Value "===== PARALLEL END failed=$($failed.Count) $(Get-Date -Format o) ====="
if ($failed.Count -gt 0) {
    foreach ($item in $failed) {
        Add-Content -LiteralPath $driverLog -Value "FAILED label=$($item.Label) stdout=$($item.Stdout) stderr=$($item.Stderr)"
    }
    exit 1
}
