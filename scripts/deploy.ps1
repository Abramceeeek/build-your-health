# Deploy Build-your-health to the server (single canonical deploy script).
#
# Usage:
#   .\scripts\deploy.ps1
#   .\scripts\deploy.ps1 -Server ubuntu@1.2.3.4 -SshKey C:\path\key -RemoteDir /home/ubuntu/health-app
#
# Defaults match the current Oracle Cloud box but can be overridden via env vars:
#   DEPLOY_SERVER, DEPLOY_SSH_KEY, DEPLOY_REMOTE_DIR
#
# IMPORTANT: this script does NOT copy .env to the server (unlike the old `scp -r .`
# flow). Provision ~/app/.env on the server once, out of band, so secrets never travel
# through this deploy. Unlike `scp -r "...\."`, this also skips .git, .claude/worktrees
# (the separate HealthOS app), the local *.db, uploads/, and caches.

param(
    [string]$Server    = $(if ($env:DEPLOY_SERVER)     { $env:DEPLOY_SERVER }     else { "ubuntu@132.145.58.45" }),
    [string]$SshKey    = $(if ($env:DEPLOY_SSH_KEY)    { $env:DEPLOY_SSH_KEY }    else { "$env:USERPROFILE\Downloads\ssh-key-2026-04-06.key" }),
    [string]$RemoteDir = $(if ($env:DEPLOY_REMOTE_DIR) { $env:DEPLOY_REMOTE_DIR } else { "/home/ubuntu/app" })
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $SshKey)) {
    Write-Error "SSH key not found: $SshKey  (set DEPLOY_SSH_KEY or pass -SshKey)"
    exit 1
}

Write-Host "Deploying to ${Server}:${RemoteDir}" -ForegroundColor Cyan

# Files/dirs the server needs. .env is intentionally excluded (provisioned server-side).
$Items = @(
    "backend", "frontend", "alembic", "scripts",
    "alembic.ini", "bot.py", "main.py",
    "requirements.txt", "requirements.lock",
    "Dockerfile", "docker-compose.yml", ".env.example"
)

# Ensure the remote dir exists.
ssh -i $SshKey $Server "mkdir -p $RemoteDir"

foreach ($item in $Items) {
    $src = Join-Path $ProjectRoot $item
    if (Test-Path $src) {
        Write-Host "  -> $item" -ForegroundColor Gray
        scp -i $SshKey -r -q "$src" "${Server}:${RemoteDir}/"
    }
}

Write-Host "Rebuilding & restarting (docker-compose v1)..." -ForegroundColor Cyan
ssh -i $SshKey $Server "cd $RemoteDir && docker-compose down --remove-orphans && docker-compose up -d --build && docker-compose ps && docker-compose logs --tail 30"

Write-Host "Deployment complete." -ForegroundColor Green
