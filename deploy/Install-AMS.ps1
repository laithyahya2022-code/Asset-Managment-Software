<#
  Install AMS as a real Windows service.

  Turns AMS.exe from "a file you double-click in Downloads" into an
  application: one fixed install folder, started automatically at boot,
  serving every device on the network, with the database in one known place
  that upgrades never touch.

  Run it by right-clicking Install-AMS.bat -> "Run as administrator", or:
      powershell -ExecutionPolicy Bypass -File Install-AMS.ps1

  Re-running it upgrades in place. The instance folder -- database, uploads,
  backups, session key -- is never written to by this script.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\AMS",
    [int]$Port = 8080,
    [string]$Source = ""      # path to AMS.exe; defaults to next to this script
)

$ErrorActionPreference = "Stop"
$TaskName = "AMS - Mada Asset Management System"

function Say($msg, $colour = "Gray") { Write-Host "  $msg" -ForegroundColor $colour }
function Fail($msg) { Write-Host ""; Write-Host "  ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Mada Asset Management System - installer" -ForegroundColor Cyan
Write-Host "  =======================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------- checks
$admin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Fail "Run this as administrator (right-click Install-AMS.bat -> Run as administrator)."
}

if (-not $Source) {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $Source = Join-Path $here "AMS.exe"
}
if (-not (Test-Path $Source)) {
    Fail "AMS.exe not found at '$Source'. Put this script next to AMS.exe, or pass -Source."
}

# ------------------------------------------------------------- install dir
$target = Join-Path $InstallDir "AMS.exe"
$instance = Join-Path $InstallDir "instance"
$upgrade = Test-Path $instance

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Say "Install folder:  $InstallDir"

if ($upgrade) {
    $db = Join-Path $instance "itam.sqlite"
    $size = if (Test-Path $db) { "{0:N1} MB" -f ((Get-Item $db).Length / 1MB) } else { "none yet" }
    Say "Existing data found - it will be left exactly as it is (database: $size)." "Green"
}

# Stop anything currently running, or the copy below fails.
Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }
Get-Process -Name "AMS" -ErrorAction SilentlyContinue |
    ForEach-Object { $_.Kill(); $_.WaitForExit(5000) }
Start-Sleep -Milliseconds 500

Copy-Item -Path $Source -Destination $target -Force
Say "Program installed."

# ------------------------------------------------------- start-at-boot task
# A scheduled task rather than NSSM: it is built into Windows, so there is
# nothing extra to download onto a school server.
$action = New-ScheduledTaskAction -Execute $target -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount `
    -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 3 `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Say "Registered to start automatically at boot."

# AMS_NO_BROWSER keeps it headless under the service account, where there is
# no desktop to draw a window on.
[Environment]::SetEnvironmentVariable("AMS_NO_BROWSER", "1", "Machine")
[Environment]::SetEnvironmentVariable("PORT", "$Port", "Machine")
Say "Configured to run headless on port $Port."

# ------------------------------------------------------------- firewall
$ruleName = "AMS (port $Port)"
Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $Port -Profile Domain,Private | Out-Null
Say "Firewall opened for port $Port on domain and private networks."

# --------------------------------------------------------------- start it
Start-ScheduledTask -TaskName $TaskName
$url = $null
foreach ($i in 1..30) {
    Start-Sleep -Milliseconds 700
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Port/login" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $url = "up"; break }
    } catch { }
}
if (-not $url) {
    Fail "AMS was installed but did not answer on port $Port. Is that port already in use? Try -Port 8090."
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -First 1).IPAddress
$address = "http://${ip}:$Port"

# Leave the address where whoever set this up can find it again.
@"
Mada Asset Management System (AMS)
==================================

Everyone opens this address in a browser:

    $address

Nobody else needs to install anything. Do not copy AMS.exe to another
computer -- a second copy is a second, empty database.

Installed:  $InstallDir
Data:       $instance   <- back up this folder
Service:    Task Scheduler -> "$TaskName"
"@ | Set-Content -Path (Join-Path $InstallDir "AMS - open on other devices.txt") -Encoding UTF8

Write-Host ""
Write-Host "  Done." -ForegroundColor Green
Write-Host ""
Write-Host "  Everyone opens:  $address" -ForegroundColor Cyan
if (-not $upgrade) {
    Write-Host "  First login:     admin / admin123  (change it immediately)" -ForegroundColor Yellow
} else {
    Write-Host "  Your existing data and logins are unchanged." -ForegroundColor Green
}
Write-Host "  Data folder:     $instance"
Write-Host "                   back this folder up; it is the whole system."
Write-Host ""
