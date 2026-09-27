param(
    [switch]$ForceRerun
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AutoDojoRoot = Join-Path $Root "external\official_baselines\AutoDojo"
$Model = "deepseek-v4-flash"
$GeometryRoot = Join-Path $Root "results\runs\clafr_review_geometry_isolation_pilot_20260721"
$AdaptiveRoot = Join-Path $Root "results\runs\clafr_review_adaptive_stress_pilot_20260721"

$Cases = [ordered]@{
    banking = @{ user = "user_task_4"; injection = "injection_task_8" }
    slack = @{ user = "user_task_10"; injection = "injection_task_1" }
    travel = @{ user = "user_task_10"; injection = "injection_task_0" }
    workspace = @{ user = "user_task_21"; injection = "injection_task_1" }
}

$GeometryDefenses = @(
    "clafr",
    "clafr_geometry_halfspace_only",
    "clafr_geometry_cone_only",
    "clafr_geometry_schema_only"
)

$AdaptiveCases = @(
    @{ attack = "clafr_provenance_spoofing"; suite = "workspace"; user = "user_task_21"; injection = "injection_task_1" },
    @{ attack = "clafr_destination_ambiguity"; suite = "slack"; user = "user_task_10"; injection = "injection_task_1" },
    @{ attack = "clafr_multistep_contamination"; suite = "banking"; user = "user_task_4"; injection = "injection_task_8" },
    @{ attack = "clafr_clarification_exploitation"; suite = "travel"; user = "user_task_10"; injection = "injection_task_0" }
)

function Load-DotEnvNoPrint {
    param([string]$Path)
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $parts = $trimmed.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim().Trim('"').Trim("'"), "Process")
    }
}

function Configure-Route {
    Load-DotEnvNoPrint -Path (Join-Path $Root ".env")
    $env:OPENAI_MODEL = $Model
    $env:OPENAI_COMPATIBLE_API_KEY = $env:OPENAI_API_KEY
    $env:OPENAI_COMPATIBLE_BASE_URL = $env:OPENAI_BASE_URL
    $env:OPENAI_COMPATIBLE_PROTOCOL = "chat_completions"
    $env:AGENTDOJO_OPENAI_TIMEOUT_SECONDS = "180"
    $env:AGENTDOJO_HTTP_RETRIES = "4"
    $env:AGENTDOJO_RUN_INJECTION_UTILITY = "0"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:NO_COLOR = "1"
    $env:TERM = "dumb"
    $env:PYTHONPATH = @(
        (Join-Path $AutoDojoRoot "agentdojo\src"),
        (Join-Path $AutoDojoRoot "agentdojo\variant_generation"),
        (Join-Path $Root "src"),
        (Join-Path $Root "src"),
        $Root
    ) -join ";"
}

function Invoke-Benchmark {
    param(
        [string]$Label,
        [string]$OutRoot,
        [string]$Suite,
        [string]$UserTask,
        [string]$InjectionTask = "",
        [string]$Attack = "",
        [string]$Defense = ""
    )
    $doneMarker = Join-Path $OutRoot "markers\$Label.done"
    if ((Test-Path -LiteralPath $doneMarker) -and -not $ForceRerun) { return }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $doneMarker) | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $OutRoot "logs") | Out-Null
    $args = @(
        "-m", "agentdojo.scripts.benchmark",
        "--model", $Model,
        "--model-id", $Model,
        "--benchmark-version", "v1.2.2",
        "--suite", $Suite,
        "--logdir", $OutRoot,
        "--user-task", $UserTask
    )
    if ($Defense) { $args += @("--defense", $Defense) }
    if ($Attack) {
        $args += @("--attack", $Attack, "--injection-task", $InjectionTask)
    }
    $log = Join-Path $OutRoot "logs\$Label.log"
    & python @args *> $log
    if ($LASTEXITCODE -ne 0) { throw "$Label failed; see $log" }
    Set-Content -LiteralPath $doneMarker -Value (Get-Date -Format o) -Encoding ascii
}

function Write-Manifests {
    New-Item -ItemType Directory -Force -Path $GeometryRoot, $AdaptiveRoot | Out-Null
    [ordered]@{
        schema = "clafr-review-geometry-isolation-pilot-v1"
        status = "diagnostic_only"
        model = $Model
        benchmark_version = "v1.2.2"
        fixed_before_run = $true
        execution_count = 32
        unique_benchmark_pairs = 8
        shared_components = @("model", "case", "evidence projection", "risk quarantine", "semantic lifting", "decision repair")
        changed_component = "geometric constraint family"
        cases = $Cases
        defenses = $GeometryDefenses
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $GeometryRoot "pilot_manifest.json") -Encoding utf8
    [ordered]@{
        schema = "clafr-review-adaptive-stress-pilot-v1"
        status = "diagnostic_only"
        model = $Model
        benchmark_version = "v1.2.2"
        fixed_before_run = $true
        execution_count = 8
        cases = $AdaptiveCases
        methods = @("no_defense", "clafr")
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $AdaptiveRoot "pilot_manifest.json") -Encoding utf8
}

Configure-Route
Write-Manifests

foreach ($defense in $GeometryDefenses) {
    foreach ($suite in $Cases.Keys) {
        $case = $Cases[$suite]
        Invoke-Benchmark -Label "geometry-$defense-$suite-clean" -OutRoot $GeometryRoot -Suite $suite -UserTask $case.user -Defense $defense
        Invoke-Benchmark -Label "geometry-$defense-$suite-attack" -OutRoot $GeometryRoot -Suite $suite -UserTask $case.user -InjectionTask $case.injection -Attack "important_instructions" -Defense $defense
    }
}

foreach ($case in $AdaptiveCases) {
    Invoke-Benchmark -Label "adaptive-no_defense-$($case.attack)" -OutRoot $AdaptiveRoot -Suite $case.suite -UserTask $case.user -InjectionTask $case.injection -Attack $case.attack
    Invoke-Benchmark -Label "adaptive-clafr-$($case.attack)" -OutRoot $AdaptiveRoot -Suite $case.suite -UserTask $case.user -InjectionTask $case.injection -Attack $case.attack -Defense "clafr"
}

python scripts\aggregate_clafr_review_pilots.py --geometry-root $GeometryRoot --adaptive-root $AdaptiveRoot
if ($LASTEXITCODE -ne 0) { throw "Pilot aggregation failed" }

