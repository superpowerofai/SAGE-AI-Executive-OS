$taskName = "SAGE Daily Recurring Generation"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed '$taskName'."
} else {
    Write-Host "No SAGE daily generation task was installed."
}
