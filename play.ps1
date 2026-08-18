#Requires -Version 5.1
<#
.SYNOPSIS
    Deploy ElderMagic locally and launch CK3 without the Paradox Launcher.
.PARAMETER Version
    Mod version string written to descriptor.mod (default: reads from ElderMagic/descriptor.mod).
.PARAMETER SkipDeploy
    Launch CK3 without re-deploying the mod files.
#>
param(
    [string]$Version,
    [switch]$SkipDeploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot  = $PSScriptRoot
$CK3Exe    = "C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\binaries\ck3.exe"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PubScript = Join-Path $RepoRoot "multi_agent_ck3\tools\publication.py"

# --- resolve version from descriptor.mod when not supplied ---
if (-not $Version) {
    $descriptorPath = Join-Path $RepoRoot "ElderMagic\descriptor.mod"
    $versionLine = Get-Content $descriptorPath | Where-Object { $_ -match '^version=' }
    $Version = ($versionLine -replace 'version="([^"]+)"', '$1').Trim()
}

# --- deploy ---
if (-not $SkipDeploy) {
    Write-Host "Deploying ElderMagic v$Version ..." -ForegroundColor Cyan
    & $PythonExe $PubScript ElderMagic --display-name "Elder Magic" --version $Version
    if ($LASTEXITCODE -ne 0) { throw "publication.py failed (exit $LASTEXITCODE)" }
}

# --- launch ---
Write-Host "Launching CK3 (skipping launcher) ..." -ForegroundColor Green
Start-Process -FilePath $CK3Exe -ArgumentList "-skiplauncher"
