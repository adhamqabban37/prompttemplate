$ErrorActionPreference = 'Stop'
Write-Host "[health] Checking backend health..."
try {
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v1/utils/health-check/" -TimeoutSec 10
  if ($resp -eq $true) { Write-Host "PASS health"; exit 0 } else { Write-Host "FAIL health: unexpected body"; exit 1 }
} catch {
  Write-Host "FAIL health: $($_.Exception.Message)"; exit 1
}