# PowerShell script to bypass Windows proxy for localhost development
# 
# Usage:
#   1. Run this script in PowerShell: .\scripts\dev-proxy-bypass.ps1
#   2. Restart your terminal/IDE for changes to take effect
#
# What it does:
#   - Sets NO_PROXY environment variable to bypass proxy for localhost
#   - Disables Windows system HTTP proxy for development
#   - Prevents "Windows Security" popups when accessing localhost APIs
#
# To revert:
#   - Run: netsh winhttp reset proxy
#   - Remove NO_PROXY from environment variables

Write-Host "Setting up development proxy bypass for localhost..." -ForegroundColor Cyan

# Set NO_PROXY environment variable for current user
[System.Environment]::SetEnvironmentVariable("NO_PROXY", "localhost,127.0.0.1", [System.EnvironmentVariableTarget]::User)
Write-Host "✓ Set NO_PROXY=localhost,127.0.0.1 for current user" -ForegroundColor Green

# Reset Windows HTTP proxy to direct connection (requires admin)
try {
    netsh winhttp reset proxy | Out-Null
    Write-Host "✓ Reset Windows HTTP proxy to direct connection" -ForegroundColor Green
} catch {
    Write-Host "⚠ Could not reset Windows HTTP proxy (try running as Administrator)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Proxy bypass configured successfully!" -ForegroundColor Green
Write-Host "Note: Restart your terminal/IDE for changes to take effect" -ForegroundColor Yellow
Write-Host ""
Write-Host "To verify: Get-Item Env:NO_PROXY" -ForegroundColor Cyan
