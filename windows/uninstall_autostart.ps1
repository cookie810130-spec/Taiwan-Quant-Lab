$ErrorActionPreference = 'Stop'
Unregister-ScheduledTask -TaskName 'TaiwanQuantLabV2' -Confirm:$false
Write-Host 'Task unregistered. No data or API keys were deleted.'
