<#
.SYNOPSIS
  Exposes the local Health Transform server via Cloudflare Quick Tunnel (HTTPS).

.DESCRIPTION
  1. Start the app first:  python main.py
  2. Run this script in another terminal.

  It reads PORT from .env in the project root (default 8000) and runs:
    cloudflared tunnel --url http://127.0.0.1:<PORT>

  Copy the https://....trycloudflare.com URL into .env as WEBAPP_URL=...
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$port = 8000
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*PORT\s*=\s*(\d+)\s*$') {
            $port = [int]$Matches[1]
        }
    }
}
if ($env:PORT) { $port = [int]$env:PORT }

$url = "http://127.0.0.1:$port"
Write-Host ""
Write-Host "  Cloudflare Quick Tunnel -> $url" -ForegroundColor Cyan
Write-Host "  Set WEBAPP_URL in .env to the https URL cloudflared prints below." -ForegroundColor Gray
Write-Host ""

# Must have FastAPI running here or the tunnel will hit the wrong service / errors
try {
    $health = Invoke-WebRequest -Uri "$url/health" -UseBasicParsing -TimeoutSec 5
    if ($health.StatusCode -ne 200 -or $health.Content -notmatch '"status"\s*:\s*"ok"') {
        throw "unexpected response"
    }
    Write-Host "  OK: $url/health returned 200 (app is running)." -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "  ERROR: No Health Transform server on $url" -ForegroundColor Red
    Write-Host "  Start the API first in another window, then run this script again:" -ForegroundColor Yellow
    Write-Host "    python main.py" -ForegroundColor White
    Write-Host ""
    exit 1
}
Write-Host ""

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    $cfPath = "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe"
    if (Test-Path $cfPath) {
        & $cfPath tunnel --url $url
    } else {
        Write-Host "cloudflared not found. Install: winget install Cloudflare.cloudflared" -ForegroundColor Red
        exit 1
    }
} else {
    & cloudflared tunnel --url $url
}
