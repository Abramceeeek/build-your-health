# Stops cloudflared (tunnel). Does NOT close Cursor/VS Code terminals — run this or Task Manager.
# After stopping, start again: python main.py, then python scripts\launch_tunnel.py --tunnel-only

$ErrorActionPreference = "SilentlyContinue"

Write-Host "Stopping cloudflared.exe ..."
taskkill /F /IM cloudflared.exe 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "cloudflared stopped."
} else {
    Write-Host "No cloudflared process found (or access denied)."
}

Write-Host ""
Write-Host "Checking for processes on port 8000 ..."
$pids = netstat -ano | Select-String ":8000\s.*LISTENING" | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Sort-Object -Unique | Where-Object { $_ -ne "0" }

if ($pids) {
    foreach ($pid in $pids) {
        Write-Host "  Killing PID $pid (bound to port 8000)"
        taskkill /F /PID $pid 2>$null | Out-Null
    }
    Write-Host "Done."
} else {
    Write-Host "  No processes found on port 8000."
}
Write-Host ""
