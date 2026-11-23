#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "  STARTING DEPLOYMENT: ML Prediction Grid Data Stack"
echo "=========================================================="

WORKSPACE_DIR="$(pwd)"
COMPOSE_FILE="${WORKSPACE_DIR}/deploy/docker-compose.prod.yml"
PROJECT_NAME="ml-prediction-stack"

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
    echo "Docker Compose not detected. Will deploy via native Docker Engine..."
fi

# 1. Cleanly stop previous stack deployment if using Compose
if [ -n "$COMPOSE_CMD" ]; then
    echo "Stopping existing ${PROJECT_NAME} containers if running..."
    $COMPOSE_CMD -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" down || true
fi

# 2. Release host port 8000 if held by any stale container
EXISTING_PORT_8000=$(docker ps -q --filter "publish=8000" || true)
if [ -n "$EXISTING_PORT_8000" ]; then
    echo "Releasing host port 8000 from container(s): ${EXISTING_PORT_8000}..."
    docker stop ${EXISTING_PORT_8000} >/dev/null 2>&1 || true
    docker rm -f ${EXISTING_PORT_8000} >/dev/null 2>&1 || true
fi

# 3. Ensure any existing container named ml-prediction-engine is completely cleared
if docker ps -a -q --filter "name=^ml-prediction-engine$" | grep -q .; then
    echo "Removing existing container named ml-prediction-engine..."
    docker stop ml-prediction-engine >/dev/null 2>&1 || true
    docker rm -f ml-prediction-engine >/dev/null 2>&1 || true
fi

# 4. Deploy the stack (Compose or native Docker fallback)
if [ -n "$COMPOSE_CMD" ]; then
    echo "Deploying via ${COMPOSE_CMD} (Project: ${PROJECT_NAME})..."
    $COMPOSE_CMD -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" up -d
else
    echo "Ensuring Docker volumes and network exist..."
    docker volume create ml_models_data >/dev/null 2>&1 || true
    docker volume create ml_logs_data >/dev/null 2>&1 || true
    docker network create ml-grid-net >/dev/null 2>&1 || true

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
