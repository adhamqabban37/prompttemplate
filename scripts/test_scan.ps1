$ErrorActionPreference = 'Stop'
param(
  [string]$Url1 = "https://example.com",
  [string]$Url2 = "https://web.dev/"
)

function Invoke-Scan($url) {
  Write-Host "[scan] $url"
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v1/scan?url=$([uri]::EscapeDataString($url))" -Method GET -TimeoutSec 180 -SkipHttpErrorCheck -ResponseHeadersVariable hdr
  if ($hdr.StatusCode -and $hdr.StatusCode -ne 200) {
    Write-Host "FAIL scan: HTTP $($hdr.StatusCode)"; return $null
  }
  return $resp
}

$a = Invoke-Scan $Url1
$b = Invoke-Scan $Url2

$pass = $true
if ($a -and $a.keyphrases -and $a.keyphrases.Count -gt 0 -and $a.timings) { Write-Host "PASS scan $Url1 (keyphrases=$($a.keyphrases.Count))" } else { Write-Host "WARN scan $Url1 (no keyphrases)"; $pass = $false }
if ($b -and $b.lighthouse -and $b.lighthouse.available -ne $null -and $b.timings) { Write-Host "PASS scan $Url2 (psi.available=$($b.lighthouse.available))" } else { Write-Host "WARN scan $Url2 (psi missing)"; $pass = $false }

if ($pass) { exit 0 } else { exit 1 }