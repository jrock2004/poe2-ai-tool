# Dev setup for Windows: builds mcp\.venv (editable, with the dev group) so the tests run.
# Players don't need this -- they install the plugin (README -> Install). Safe to re-run.
# Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# -ExecutionPolicy Bypass applies to this one run only; it changes no system setting.
# It does not install Python: it checks for 3.10+ and tells you how if it's missing.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Native commands don't throw on failure in Windows PowerShell; check the exit code ourselves.
function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Failed ($LASTEXITCODE): $Exe $($Arguments -join ' ')" }
}

# Prefer the py launcher: a bare `python` may be Windows' Microsoft Store alias.
$Python = $null
foreach ($candidate in @(@("py", "-3"), @("python"))) {
    if (Get-Command $candidate[0] -ErrorAction SilentlyContinue) {
        $rest = @($candidate | Select-Object -Skip 1)
        & $candidate[0] @rest -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Python = $candidate; break }
    }
}
if (-not $Python) {
    Write-Error ("Python 3.10+ not found. Install it with: winget install Python.Python.3.13 " +
                 "(or from python.org, ticking 'Add python.exe to PATH'), then re-run.")
}
$PyExe = $Python[0]
$PyRest = @($Python | Select-Object -Skip 1)
Write-Host "==> Using $(& $PyExe @PyRest --version)"

Write-Host "==> Installing the MCP server into mcp\.venv"
$VenvPython = Join-Path $Root "mcp\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) { Invoke-Checked $PyExe ($PyRest + @("-m", "venv", "mcp\.venv")) }
Invoke-Checked $VenvPython @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
# --group reads pyproject.toml from the current directory, so install from inside mcp\.
Push-Location (Join-Path $Root "mcp")
try { Invoke-Checked $VenvPython @("-m", "pip", "install", "--quiet", "-e", ".", "--group", "dev") }
finally { Pop-Location }

Write-Host "==> Checking the server imports"
Invoke-Checked $VenvPython @("-c", "import poe2_mcp.server")
Write-Host "    ok"

# The pre-plugin setup wired the server and skills in per project; with the plugin installed too,
# both would load twice. Point it out rather than deleting anything.
if ((Test-Path (Join-Path $Root ".mcp.json")) -or (Test-Path (Join-Path $Root ".claude\skills"))) {
    Write-Host ""
    Write-Host "Note: .mcp.json and/or .claude\skills are left over from the old setup. Delete them once the"
    Write-Host "plugin is installed, or the poe2 server and skills load twice."
}

Write-Host ""
Write-Host "Done. Run the tests with: cd mcp; .venv\Scripts\python -m pytest -q"
Write-Host "To use your working copy in Claude Code, add it as a local marketplace (README -> Development)."
