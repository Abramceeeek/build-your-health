# Deploy Health Transform to Oracle Cloud (PowerShell)
# Usage: .\scripts\deploy.ps1

$ErrorActionPreference = "Stop"

# ── Configuration ──────────────────────────────
$Server = "ubuntu@132.145.58.45"
$SSHKey = "$env:USERPROFILE\.ssh\oracle_key"
$RemoteDir = "/home/ubuntu/health-app"

Write-Host "🚀 Deploying Health Transform..." -ForegroundColor Cyan

# ── Sync files using scp (rsync alternative for Windows) ──
Write-Host "📦 Syncing files to server..." -ForegroundColor Yellow

# Create exclude list
$ExcludeDirs = @('.env', '__pycache__', '*.pyc', '*.db', 'data', 'uploads', '.git', 'node_modules', '.venv')

# Use scp for key directories
$Dirs = @('backend', 'frontend', 'alembic', 'scripts')
$Files = @('main.py', 'bot.py', 'alembic.ini', 'Dockerfile', 'docker-compose.yml', 'requirements.txt')

foreach ($dir in $Dirs) {
    Write-Host "  Copying $dir/..." -ForegroundColor Gray
    scp -i $SSHKey -r "./$dir" "${Server}:${RemoteDir}/"
}

foreach ($file in $Files) {
    if (Test-Path $file) {
        Write-Host "  Copying $file..." -ForegroundColor Gray
        scp -i $SSHKey "./$file" "${Server}:${RemoteDir}/"
    }
}

# ── Rebuild and restart ───────────────────────
Write-Host "🔨 Rebuilding on server..." -ForegroundColor Yellow
ssh -i $SSHKey $Server "cd $RemoteDir && docker compose down && docker compose up -d --build && echo '✅ Done!' && docker compose logs --tail 20"

Write-Host "🎉 Deployment complete!" -ForegroundColor Green
