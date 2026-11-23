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

# Detect Docker Compose capability safely
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    echo "Using Docker Compose V2 plugin (docker compose)..."
elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    echo "Using standalone Docker Compose (docker-compose)..."
else
    echo "Docker Compose plugin/binary not detected. Deploying via native Docker Engine..."
fi

if [ -n "$COMPOSE_CMD" ]; then
    echo "Deploying via ${COMPOSE_CMD}..."
    $COMPOSE_CMD -f "${COMPOSE_FILE}" pull --ignore-buildable || true
    $COMPOSE_CMD -f "${COMPOSE_FILE}" up -d --remove-orphans
else
    echo "Ensuring Docker volumes and network exist..."
    docker volume create ml_models_data >/dev/null 2>&1 || true
    docker volume create ml_logs_data >/dev/null 2>&1 || true
    docker network create ml-grid-net >/dev/null 2>&1 || true

    echo "Stopping any existing container..."
    docker stop ml-prediction-engine >/dev/null 2>&1 || true
    docker rm -f ml-prediction-engine >/dev/null 2>&1 || true

    echo "Launching container ml-prediction-engine:latest..."
    docker run -d \
        --name ml-prediction-engine \
        --restart unless-stopped \
        -p 8000:8000 \
        -e HOST=0.0.0.0 \
        -e PORT=8000 \
        -e ENVIRONMENT=production \
        -e LOG_LEVEL=INFO \
        -e CONFIG_PATH=config/config.yaml \
        -e MODEL_CONFIG_PATH=config/model_config.yaml \
        -v ml_models_data:/app/models_artifacts \
        -v ml_logs_data:/app/logs \
        --network ml-grid-net \
        ml-prediction-engine:latest
fi

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
    docker logs ml-prediction-engine --tail=50 || true
    exit 1
fi

echo "Pruning unused builder cache and old images..."
docker image prune -f || true

echo "=========================================================="
echo "✅ DEPLOYMENT SUCCEEDED: Service running on http://127.0.0.1:8000"
echo "=========================================================="
