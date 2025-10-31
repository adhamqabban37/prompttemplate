$ErrorActionPreference = 'Stop'
$Url = 'https://www.garciamullen.com/portal'
$body = @{ target_url = $Url; free_test_mode = $true } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri 'http://localhost:8001/api/v1/orchestrator/run' -Method Post -ContentType 'application/json' -Body $body
$resp | ConvertTo-Json -Depth 6 | Set-Content -Path "$PSScriptRoot/orchestrator_last.json"
Write-Host "status:" $resp.status
Write-Host "title:" $resp.content.title
Write-Host "final_url:" $resp.target.final_url
Write-Host "http_status:" $resp.target.http_status
