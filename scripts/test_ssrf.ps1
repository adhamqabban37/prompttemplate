$ErrorActionPreference = 'Stop'
param(
  [string]$Url = "http://127.0.0.1:22"
)
Write-Host "[ssrf] Expect 400 for $Url"
$hdr = $null
try {
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v1/scan?url=$Url" -Method GET -SkipHttpErrorCheck -ResponseHeadersVariable hdr
  if ($hdr.StatusCode -eq 400 -or $resp.detail) { Write-Host "PASS ssrf"; exit 0 } else { Write-Host "FAIL ssrf: $($hdr.StatusCode)"; exit 1 }
} catch {
  Write-Host "FAIL ssrf: $($_.Exception.Message)"; exit 1
}