# ==============================================================================
# Argos - One-line Installer for Windows PowerShell
# Usage:
#   irm https://raw.githubusercontent.com/your-repo/argos-agent/main/install.ps1 | iex
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ARGOS - Multi-Agent Remote Orchestrator Installer" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

$argosHome = Join-Path $HOME ".argos"
$binDir = Join-Path $argosHome "bin"
$venvDir = Join-Path $argosHome "venv"

New-Item -ItemType Directory -Force -Path $argosHome | Out-Null
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

# 1. Detect Python
$pythonCmd = $null
foreach ($cmd in @("python", "py", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -or $ver -match "Python 3") {
            $pythonCmd = $cmd
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "[Error] Python 3.9+ was not detected on your system." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/ or run 'winget install Python.Python.3.11'." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] Detected Python: $(& $pythonCmd --version)" -ForegroundColor Green

# 2. Check if local dev repo is being installed or PyPI package
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$localDevRepo = $false
if ($scriptDir -and (Test-Path (Join-Path $scriptDir "pyproject.toml"))) {
    $localDevRepo = $true
}

Write-Host "[2/4] Setting up isolated runtime environment at $venvDir ..." -ForegroundColor Green

$hasUv = $false
try {
    $uvVer = uv --version 2>&1
    if ($LASTEXITCODE -eq 0) { $hasUv = $true }
} catch {}

if ($hasUv) {
    uv venv $venvDir | Out-Null
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if ($localDevRepo) {
        uv pip install -e $scriptDir --python $venvPython
    } else {
        uv pip install argos-agent --python $venvPython
    }
} else {
    & $pythonCmd -m venv $venvDir
    $venvPip = Join-Path $venvDir "Scripts\pip.exe"
    if ($localDevRepo) {
        & $venvPip install -e $scriptDir
    } else {
        & $venvPip install argos-agent
    }
}

# 3. Create argos.cmd and argos.ps1 wrapper in ~/.argos/bin
Write-Host "[3/4] Creating global command runner scripts..." -ForegroundColor Green
$targetExe = Join-Path $venvDir "Scripts\argos.exe"

$cmdContent = "@echo off`r`n`"$targetExe`" %*`r`n"
Set-Content -Path (Join-Path $binDir "argos.cmd") -Value $cmdContent -Encoding ASCII

$ps1Content = "& `"$targetExe`" @args`r`n"
Set-Content -Path (Join-Path $binDir "argos.ps1") -Value $ps1Content -Encoding ASCII

# Also create server-helper.cmd alias for backwards compatibility
$shContent = "@echo off`r`n`"$targetExe`" %*`r`n"
Set-Content -Path (Join-Path $binDir "server-helper.cmd") -Value $shContent -Encoding ASCII

# 4. Add binDir to Windows User PATH
Write-Host "[4/4] Configuring Windows User PATH environment variable..." -ForegroundColor Green
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }

$pathParts = $userPath -split ';'
if ($pathParts -notcontains $binDir) {
    $newPath = if ($userPath.EndsWith(';')) { "$userPath$binDir" } else { "$userPath;$binDir" }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "[Info] Successfully added $binDir to Windows User PATH!" -ForegroundColor Cyan
} else {
    Write-Host "[Info] $binDir is already present in User PATH." -ForegroundColor Cyan
}

# Also copy into npm global bin directory if present for instant access without restarting terminal
$npmGlobal = "D:\nodejs\node_global"
if (Test-Path $npmGlobal) {
    Copy-Item -Path (Join-Path $binDir "argos.cmd") -Destination (Join-Path $npmGlobal "argos.cmd") -Force
    Copy-Item -Path (Join-Path $binDir "argos.ps1") -Destination (Join-Path $npmGlobal "argos.ps1") -Force
    Write-Host "[Info] Copied argos.cmd to npm global directory: $npmGlobal" -ForegroundColor Cyan
}

Write-Host "`n[Success] Argos installed successfully!" -ForegroundColor Green
Write-Host "You can now open ANY terminal and directly type:" -ForegroundColor Yellow
Write-Host "   argos`n" -ForegroundColor Cyan
