#!/bin/bash
# Deploy Health Transform to Oracle Cloud
# Usage: bash scripts/deploy.sh

set -e

# ── Configuration ──────────────────────────────
SERVER="ubuntu@132.145.58.45"
SSH_KEY="~/.ssh/oracle_key"
REMOTE_DIR="/home/ubuntu/health-app"

echo "🚀 Deploying Health Transform..."

# ── Sync files ────────────────────────────────
echo "📦 Syncing files to server..."
rsync -avz --progress \
  --exclude '.env' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.db' \
  --exclude 'data/' \
  --exclude 'uploads/' \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '.venv' \
  -e "ssh -i $SSH_KEY" \
  ./ "$SERVER:$REMOTE_DIR/"

# ── Rebuild and restart ───────────────────────
echo "🔨 Rebuilding on server..."
ssh -i "$SSH_KEY" "$SERVER" << 'EOF'
cd /home/ubuntu/health-app
docker compose down
docker compose up -d --build
echo "✅ Deployment complete!"
docker compose logs --tail 20
EOF

echo "🎉 Done! App should be live."
