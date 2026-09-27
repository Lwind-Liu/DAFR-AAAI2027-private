param(
    [switch]$ForceRerun,
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\results\deepseek32_asb_paper_baselines"),
    [string[]]$Variants = @("baseline", "prompt_policy", "clafr_full", "progent", "drift")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $Root
$ModelId = "deepseek-v4-flash"

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

Load-DotEnvNoPrint -Path (Join-Path $Root ".env")
[Environment]::SetEnvironmentVariable("OPENAI_MODEL", $ModelId, "Process")
[Environment]::SetEnvironmentVariable("OPENAI_COMPATIBLE_API_KEY", $env:OPENAI_API_KEY, "Process")
[Environment]::SetEnvironmentVariable("OPENAI_COMPATIBLE_BASE_URL", $env:OPENAI_BASE_URL, "Process")
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "Process")
[Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "Process")

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
$PythonArgs = @(
    "ICLR\scripts\run_asb_clafr_agent_score.py",
    "--output-dir", $OutRoot,
    "--model-id", $ModelId,
    "--task-nums", "2",
    "--attack-limit", "4",
    "--max-cases", "32",
    "--max-turns", "8",
    "--timeout-seconds", "120",
    "--retries", "2",
    "--variants"
) + $Variants
if ($ForceRerun) {
    $PythonArgs += @("--force-rerun")
}
python @PythonArgs
