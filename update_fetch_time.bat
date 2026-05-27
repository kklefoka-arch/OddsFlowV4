@echo off
powershell -Command "$t = New-ScheduledTaskTrigger -Daily -At '01:00'; Set-ScheduledTask -TaskName 'OddsFlow_FetchUpcoming' -Trigger $t"
echo Done - FetchUpcoming now runs at 01:00
pause
