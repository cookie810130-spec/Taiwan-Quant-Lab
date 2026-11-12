# Task Scheduler runner, independent of API / VPN.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$py = Join-Path $root '.venv-v2\Scripts\python.exe'
$logDirectory = Join-Path $root 'data\v2'
New-Item -Force -ItemType Directory -Path $logDirectory | Out-Null
$log = Join-Path $logDirectory 'daily.log'
Push-Location $root
try {
    Add-Content -Path $log -Value "==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') v2.1 scheduled run ===="
    & $py -m quantlab.v2.daily *>> $log
    if ($LASTEXITCODE -ne 0) { throw "V2.1 daily returned exit code $LASTEXITCODE; inspect $log" }
} finally {
    Pop-Location
}
