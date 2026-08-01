<#
  Remove the AMS service, firewall rule and program.

  Your data is NOT deleted. The instance folder -- database, uploads,
  backups -- is left in place, and this script tells you where it is.
  Deleting it is a deliberate act you have to do yourself.

      powershell -ExecutionPolicy Bypass -File Uninstall-AMS.ps1
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\AMS",
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$TaskName = "AMS - Mada Asset Management System"

$admin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host "  Run this as administrator." -ForegroundColor Red
    exit 1
}

Write-Host ""
Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  Service removed." -ForegroundColor Gray
}
Get-Process -Name "AMS" -ErrorAction SilentlyContinue | ForEach-Object { $_.Kill() }

Get-NetFirewallRule -DisplayName "AMS (port $Port)" -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule
Write-Host "  Firewall rule removed." -ForegroundColor Gray

[Environment]::SetEnvironmentVariable("AMS_NO_BROWSER", $null, "Machine")
[Environment]::SetEnvironmentVariable("PORT", $null, "Machine")

$exe = Join-Path $InstallDir "AMS.exe"
if (Test-Path $exe) { Remove-Item $exe -Force; Write-Host "  Program removed." -ForegroundColor Gray }

$instance = Join-Path $InstallDir "instance"
Write-Host ""
if (Test-Path $instance) {
    Write-Host "  Your data has been LEFT IN PLACE:" -ForegroundColor Yellow
    Write-Host "      $instance"
    Write-Host "  Copy it somewhere safe, or delete it yourself when you are sure."
} else {
    Write-Host "  No data folder found at $instance." -ForegroundColor Gray
}
Write-Host ""
