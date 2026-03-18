#!/bin/bash

# ==============================================================================
# REMOTE DEPLOYMENT SCRIPT
# - Run from project root on the server
# - Executed via CI/CD over SSH
# - Make it executable: chmod +x deploy.sh
# ==============================================================================

set -e

# --- settings ---
MAIN_BRANCH="master"
COMPOSE_FILE="docker-compose.yml"
# -----------------

TARGETS_TO_DEPLOY="$1"

echo "========================================================"
echo "Starting deployment process..."
echo "========================================================"

# 1. Pull latest changes from git repository (SSH deploy key)
echo "1. Pulling latest changes from git repository..."
GIT_HOST="${GIT_HOST:-}"
GIT_SSH_PORT="${GIT_SSH_PORT:-2222}"
GIT_REPO="${GIT_REPO:-}"

if [ -z "${GIT_HOST}" ] || [ -z "${GIT_REPO}" ]; then
  echo "GIT_HOST and GIT_REPO must be set for deployment"
  exit 1
fi

# Force SSH port without requiring ~/.ssh/config
export GIT_SSH_COMMAND="ssh -p ${GIT_SSH_PORT}"

git remote set-url origin "git@${GIT_HOST}:${GIT_REPO}"
git fetch origin
git reset --hard origin/${MAIN_BRANCH}
git pull origin ${MAIN_BRANCH}
echo "Repository updated successfully."
echo "--------------------------------------------------------"

# 2. Check deployment targets
if [ -z "$TARGETS_TO_DEPLOY" ]; then
  echo "2. No services to deploy. Exiting."
  exit 0
fi

echo "2. Deployment targets received: ${TARGETS_TO_DEPLOY}"
echo "--------------------------------------------------------"

# 3. Deploy services (Docker Compose)
SERVICES=$(echo "$TARGETS_TO_DEPLOY" | tr ',' ' ')

echo "3. Pulling latest images for: ${SERVICES}"
docker compose -f "${COMPOSE_FILE}" pull ${SERVICES}
echo " "
echo "Rebuilding and restarting services: ${SERVICES}"
docker compose -f "${COMPOSE_FILE}" up -d --build ${SERVICES}
echo "--------------------------------------------------------"

echo "========================================================"
echo "Deployment finished successfully."
echo "========================================================"
