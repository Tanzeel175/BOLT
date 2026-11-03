<#
.SYNOPSIS
    Creates Windows 11 Desktop and Start Menu shortcuts for BOLT.

.DESCRIPTION
    Installs a desktop shortcut and optional Start Menu shortcut pointing to
    the compiled BOLT executable (dist\BOLT\BOLT.exe) or the Python launcher (run.bat).
    Sets the custom BOLT icon and working directory.

.PARAMETER TargetPath
    Path to the BOLT executable or batch launcher. If not specified, auto-detects dist\BOLT\BOLT.exe or run.bat.

.PARAMETER Desktop
    Switch to create shortcut on Desktop (Default: true).

.PARAMETER StartMenu
    Switch to create shortcut in Start Menu Programs folder.
#>

param(
    [string]$TargetPath = "",
    [switch]$Desktop = $true,
    [switch]$StartMenu = $true
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ExeDistPath = Join-Path $ProjectRoot "dist\BOLT\BOLT.exe"
$BatPath = Join-Path $ProjectRoot "run.bat"
$IconPath = Join-Path $ProjectRoot "assets\bolt_icon.ico"

# Resolve Target Path
if (-not $TargetPath) {
    if (Test-Path $ExeDistPath) {
        $TargetPath = $ExeDistPath
    } elseif (Test-Path $BatPath) {
        $TargetPath = $BatPath
    } else {
        $TargetPath = Join-Path $ProjectRoot "run.py"
    }
}

Write-Host "Creating BOLT shortcuts..." -ForegroundColor Cyan
Write-Host "  Target: $TargetPath" -ForegroundColor Gray
Write-Host "  Icon:   $IconPath" -ForegroundColor Gray

$WshShell = New-Object -ComObject WScript.Shell

function Create-ShortcutInternal([string]$DestinationPath, [string]$Target, [string]$WorkingDir, [string]$Icon) {
    $Shortcut = $WshShell.CreateShortcut($DestinationPath)
    $Shortcut.TargetPath = $Target
    $Shortcut.WorkingDirectory = $WorkingDir
    $Shortcut.Description = "BOLT - Personal Autonomous AI Assistant for Windows 11"
    if (Test-Path $Icon) {
        $Shortcut.IconLocation = "$Icon, 0"
    }
    $Shortcut.Save()
    Write-Host "  [OK] Created: $DestinationPath" -ForegroundColor Green
}

# 1. Desktop Shortcut
if ($Desktop) {
    $DesktopFolder = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $DesktopShortcut = Join-Path $DesktopFolder "BOLT Assistant.lnk"
    Create-ShortcutInternal -DestinationPath $DesktopShortcut -Target $TargetPath -WorkingDir $ProjectRoot -Icon $IconPath
}

# 2. Start Menu Shortcut
if ($StartMenu) {
    $ProgramsFolder = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Programs)
    $BoltProgramsFolder = Join-Path $ProgramsFolder "BOLT Systems"
    if (-not (Test-Path $BoltProgramsFolder)) {
        New-Item -ItemType Directory -Path $BoltProgramsFolder -Force | Out-Null
    }
    $StartMenuShortcut = Join-Path $BoltProgramsFolder "BOLT Assistant.lnk"
    Create-ShortcutInternal -DestinationPath $StartMenuShortcut -Target $TargetPath -WorkingDir $ProjectRoot -Icon $IconPath
}

Write-Host "`nBOLT shortcut installation complete." -ForegroundColor Green
