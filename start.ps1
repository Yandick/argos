# ServerHelper - PowerShell Launcher
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ServerHelper - 本地 Agent 远程多任务工作台" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$helperExe = Join-Path $scriptDir ".venv\Scripts\server-helper.exe"

if (-not (Test-Path $helperExe)) {
    Write-Host "[提示] 正在初始化环境并安装项目包..." -ForegroundColor Yellow
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv venv
        uv pip install -e .
    } else {
        python -m venv .venv
        & "$scriptDir\.venv\Scripts\pip.exe" install -e .
    }
}

& $helperExe @args
