# One-time per-user 17:30 local Taiwan-time weekday schedule.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$py = Join-Path $root '.venv-v2\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'V2 Python not found. Run install_v2.bat first.' }
$timezone = (Get-TimeZone).Id
if ($timezone -ne 'Taipei Standard Time') {
    throw "Windows timezone is '$timezone'; set Taipei Standard Time first."
}
$script = Join-Path $root 'windows\run_v21_daily.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $script + '"'
) -WorkingDirectory $root
# Explicit typed DayOfWeek array and DateTime avoid argument binding on some Win10 PowerShell 5.1 locales.
$weekdays = @([System.DayOfWeek]::Monday, [System.DayOfWeek]::Tuesday, [System.DayOfWeek]::Wednesday, [System.DayOfWeek]::Thursday, [System.DayOfWeek]::Friday)
$runAt = [datetime]::Today.AddHours(17).AddMinutes(30)
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $weekdays -At $runAt
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel LeastPrivilege
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName 'TaiwanQuantLabV21Daily' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
Write-Host 'Installed: TaiwanQuantLabV21Daily (17:30 Taipei, Mon-Fri, current logged-in user)'
Write-Host 'For immediate test: Start-ScheduledTask -TaskName TaiwanQuantLabV21Daily'
Write-Host 'Log: data\v2\daily.log'
