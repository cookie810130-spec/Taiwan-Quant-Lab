$ErrorActionPreference = 'Stop'
Unregister-ScheduledTask -TaskName 'TaiwanQuantLabV21Daily' -Confirm:$false
Write-Host 'V2.1 daily task removed; data and forecast history are unchanged.'
