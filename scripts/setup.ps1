# Per-machine setup for Windows. Safe to re-run (e.g. after a new skill is added).
#   1. installs the MCP server into mcp\.venv (editable, with the dev group)
#   2. writes .mcp.json pointing at it -- only if .mcp.json doesn't exist yet
#   3. links every skill under skills\ into .claude\skills as directory junctions
#      (junctions need no admin rights or Developer Mode, unlike symlinks)
# Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 [-League "League Name"]
# -ExecutionPolicy Bypass applies to this one run only; it changes no system setting.
# It does not install Python: it checks for 3.10+ and tells you how if it's missing.
param([string]$League = "Forbidden Rites")
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

$McpJson = Join-Path $Root ".mcp.json"
if (Test-Path $McpJson) {
    Write-Host "==> .mcp.json already exists; leaving it as is"
} else {
    Write-Host "==> Writing .mcp.json (league: $League)"
    $config = @{ mcpServers = @{ poe2 = @{
        command = (Join-Path $Root "mcp\.venv\Scripts\poe2-mcp.exe")
        env     = @{ POE2_LEAGUE = $League }
    } } }
    # UTF-8 without a BOM: Windows PowerShell's own UTF8 encoding adds one, which can break JSON readers.
    $json = ($config | ConvertTo-Json -Depth 5) + "`n"
    [System.IO.File]::WriteAllText($McpJson, $json, (New-Object System.Text.UTF8Encoding $false))
}

Write-Host "==> Linking skills into .claude\skills"
$SkillsLinks = Join-Path $Root ".claude\skills"
New-Item -ItemType Directory -Force $SkillsLinks | Out-Null
Get-ChildItem (Join-Path $Root "skills") -Directory | ForEach-Object {
    $link = Join-Path $SkillsLinks $_.Name
    if (-not (Test-Path $link)) { New-Item -ItemType Junction -Path $link -Target $_.FullName | Out-Null }
    Write-Host "    $($_.Name)"
}

Write-Host "==> Checking the server imports"
Invoke-Checked $VenvPython @("-c", "import poe2_mcp.server")
Write-Host "    ok"

Write-Host ""
Write-Host "Done. Open this folder in Claude Code (or restart the session) and approve the 'poe2' server."
