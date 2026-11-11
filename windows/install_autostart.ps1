# Register per-user logon task; does NOT run before a user logs in.
# Run once AFTER install_v2.bat. The Python process has no visible console.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$py = Join-Path $root '.venv-v2\Scripts\pythonw.exe'
if (-not (Test-Path $py)) { throw "Python not found. Run install_v2.bat first." }
$action = New-ScheduledTaskAction -Execute $py -Argument '-m quantlab.v2.background' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel LeastPrivilege
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName 'TaiwanQuantLabV2' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
Write-Host 'Registered TaiwanQuantLabV2 (runs at Windows user logon).'
Write-Host 'To start now: Start-ScheduledTask -TaskName TaiwanQuantLabV2'
Write-Host 'Log: %LOCALAPPDATA%\TaiwanQuantLab\server.log'
