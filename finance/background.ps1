param(
    [Parameter(Mandatory=$true)][ValidateSet("Install","Start","Stop","Status","Remove","Run")][string]$Action,
    [switch]$BrowserDemo
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
$workspace = Join-Path $HOME "Neuravale-finance-desktop-demo"
$task = "NeuravaleFinanceDesktop-" + [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$script = $PSCommandPath
if ($Action -eq "Run") {
    if (-not (Test-Path -LiteralPath $python)) { throw "Python environment missing." }
    New-Item -ItemType Directory -Force -Path $workspace | Out-Null
    Set-Location -LiteralPath $repo
    $argsList = @("-u","-m","finance.worker","--workspace",$workspace,"serve","--port","8766")
    if ($BrowserDemo) { $argsList += "--browser-demo" }
    # This process is the scheduled task action. The worker stays local.
    & $python @argsList *>> (Join-Path $workspace "background.log")
    exit $LASTEXITCODE
}
switch ($Action) {
    "Install" {
        if (-not (Test-Path -LiteralPath $python)) { throw "Python environment missing." }
        if (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue) { throw "Already installed; remove it before changing settings." }
        $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $arguments = '-NoProfile -WindowStyle Hidden -File "' + $script + '" -Action Run'
        if ($BrowserDemo) { $arguments += " -BrowserDemo" }
        $exe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        $act = New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $repo
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $task -Action $act -Trigger $trigger -Principal $principal -Settings $settings -Description "Neuravale Finance fictional-data local worker. No live financial accounts." | Out-Null
        Write-Host "Installed for this Windows user. Run -Action Start to start now. Stop the desktop-owned worker first."
    }
    "Start" { Start-ScheduledTask -TaskName $task; Write-Host "Start requested. Check Status and the local dashboard." }
    "Stop" { Stop-ScheduledTask -TaskName $task; Write-Host "Stop requested. Check Status." }
    "Status" { Get-ScheduledTask -TaskName $task | Select-Object TaskName,State; Get-ScheduledTaskInfo -TaskName $task }
    "Remove" {
        Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $task -Confirm:$false
        Write-Host "Startup task removed. Local reports and evidence were not deleted."
    }
}
