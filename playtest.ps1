#Requires -Version 5.1
<#
.SYNOPSIS
    Deploy the Elder Magic mods as local playtest copies and launch CK3.
.DESCRIPTION
    Wraps multi_agent_ck3/tools/playtest.py. The mods are installed under separate
    "Playtest" identities without a remote_file_id, so the Steam-published copies of
    the same mods cannot shadow the local build.
.PARAMETER NoLaunch
    Deploy and set the load order without starting the game.
.PARAMETER Restore
    Restore the original load order and delete the playtest copies.
.PARAMETER AllowGuiDrift
    Deploy even when the forked .gui copies disagree on Elder Magic content.
#>
param(
    [switch]$NoLaunch,
    [switch]$Restore,
    [switch]$AllowGuiDrift
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$Script    = Join-Path $PSScriptRoot "multi_agent_ck3\tools\playtest.py"

$ScriptArgs = @()
if ($NoLaunch)      { $ScriptArgs += "--no-launch" }
if ($Restore)       { $ScriptArgs += "--restore" }
if ($AllowGuiDrift) { $ScriptArgs += "--allow-gui-drift" }

& $PythonExe $Script @ScriptArgs
exit $LASTEXITCODE
