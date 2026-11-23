$ErrorActionPreference = "Stop"
$taskName = "SAGE Daily Recurring Generation"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root "run_sage_daily.ps1"

if (-not (Test-Path $runner)) { throw "SAGE daily runner not found: $runner" }

$timeText = Read-Host "Daily generation time in 24-hour HH:mm format [08:00]"
if ([string]::IsNullOrWhiteSpace($timeText)) { $timeText = "08:00" }
if ($timeText -notmatch '^(?:[01]\d|2[0-3]):[0-5]\d$') {
    throw "Invalid time. Use 24-hour HH:mm, for example 08:00 or 18:30."
}

$runAt = [datetime]::Today.AddHours([int]$timeText.Substring(0, 2)).AddMinutes([int]$timeText.Substring(3, 2))
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $runner + '"')
$trigger = New-ScheduledTaskTrigger -Daily -At $runAt
$principalName = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { "$env:COMPUTERNAME\$env:USERNAME" }
$principal = New-ScheduledTaskPrincipal -UserId $principalName -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Generate due SAGE recurring tasks and financial obligations. Does not pay or collect money." -Force | Out-Null
Write-Host "Installed '$taskName' for $timeText daily."
Write-Host "Runs only while your Windows user is logged in; missed runs start when available."
Write-Host "Log: $root\runtime\logs\daily-generation.log"
