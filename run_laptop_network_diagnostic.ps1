param(
  [string]$User = "younis",
  [string]$Host = "192.168.1.108",
  [switch]$Fix
)

$scriptPath = "~/laptop_network_diagnostic.sh"
$localScript = "./laptop_network_diagnostic.sh"

if (-not (Test-Path $localScript)) {
  Write-Error "Cannot find $localScript"
  exit 1
}

Write-Host "Uploading diagnostic script..."
scp $localScript "$User@$Host`:$scriptPath"
if ($LASTEXITCODE -ne 0) {
  Write-Error "SCP failed. Laptop may still be unreachable."
  exit 1
}

$mode = if ($Fix.IsPresent) { "--fix" } else { "" }
$cmd = "chmod +x $scriptPath && bash $scriptPath $mode"

Write-Host "Running diagnostics on laptop..."
ssh "$User@$Host" $cmd
if ($LASTEXITCODE -ne 0) {
  Write-Error "SSH command failed."
  exit 1
}
