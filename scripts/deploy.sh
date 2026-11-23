#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "  STARTING DEPLOYMENT: ML Prediction Grid Data Stack"
echo "=========================================================="

WORKSPACE_DIR="$(pwd)"
COMPOSE_FILE="${WORKSPACE_DIR}/deploy/docker-compose.prod.yml"

# Ensure log directory exists
mkdir -p "${WORKSPACE_DIR}/logs"

# Ensure environment variables are loaded
if [ ! -f "${WORKSPACE_DIR}/.env" ]; then
    if [ -f "${WORKSPACE_DIR}/deploy/production.env.example" ]; then
        echo "Creating .env from deploy/production.env.example..."
        cp "${WORKSPACE_DIR}/deploy/production.env.example" "${WORKSPACE_DIR}/.env"
    fi
fi

# Build and deploy the container stack
echo "Deploying Docker Compose stack..."
docker compose -f "${COMPOSE_FILE}" pull --ignore-buildable || true
docker compose -f "${COMPOSE_FILE}" up -d --build --remove-orphans

echo "Waiting for ML Prediction Engine to initialize..."
MAX_RETRIES=20
COUNT=0
HEALTHY=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/health || true)
    if [ "$HTTP_CODE" = "200" ]; then
        HEALTHY=true
        break
    fi
    echo "Waiting for ML Prediction API healthcheck (attempt $((COUNT + 1))/$MAX_RETRIES, status: $HTTP_CODE)..."
    sleep 3
    COUNT=$((COUNT + 1))
done

if [ "$HEALTHY" = false ]; then
    echo "❌ Deployment failed: API did not become healthy within the timeout period."
    docker compose -f "${COMPOSE_FILE}" logs --tail=50
    exit 1
fi

echo "Pruning unused builder cache and old images..."
docker image prune -f || true

echo "=========================================================="
echo "✅ DEPLOYMENT SUCCEEDED: Service running on http://127.0.0.1:8000"
echo "=========================================================="
