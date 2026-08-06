# register-autostart.ps1
# 註冊 Windows 登入排程任務「TradingAgents-Autostart」，開機/登入時跑 autostart-stack.ps1。
# 執行一次即可（PowerShell）：  ./scripts/register-autostart.ps1
# 移除：  Unregister-ScheduledTask -TaskName 'TradingAgents-Autostart' -Confirm:$false

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "autostart-stack.ps1"
if (-not (Test-Path $script)) { throw "找不到 $script" }

$taskName = "TradingAgents-Autostart"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
# 登入後延遲 30 秒觸發，讓 Docker Desktop 的登入自啟先開始
$trigger = New-ScheduledTaskTrigger -AtLogOn
$trigger.Delay = "PT30S"
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "已註冊排程任務：$taskName（登入後 +30s 觸發 autostart-stack.ps1）" -ForegroundColor Green
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
