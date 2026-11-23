#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "  STARTING DEPLOYMENT: ML Prediction Grid Data Stack"
echo "=========================================================="

WORKSPACE_DIR="$(pwd)"
COMPOSE_FILE="${WORKSPACE_DIR}/deploy/docker-compose.prod.yml"
PROJECT_NAME="ml-prediction-stack"
TARGET_PORT="${APP_PORT:-8000}"

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

# 1. Cleanly stop previous stack deployments (both current and legacy project names)
if [ -n "$COMPOSE_CMD" ]; then
    echo "Tearing down any existing compose projects (${PROJECT_NAME}, deploy)..."
    $COMPOSE_CMD -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" down || true
    $COMPOSE_CMD -p "deploy" -f "${COMPOSE_FILE}" down || true
fi

# 2. Release host port from ALL containers (running, stopped, created, exited in docker ps -a)
echo "Scanning for any containers holding host port ${TARGET_PORT} in docker ps -a..."
OLD_PORT_CONTAINERS=$(docker ps -a --format '{{.ID}} {{.Ports}}' | grep -E "(:${TARGET_PORT}->|:::${TARGET_PORT}->)" | awk '{print $1}' || true)
if [ -n "$OLD_PORT_CONTAINERS" ]; then
    echo "Force-removing container(s) holding host port ${TARGET_PORT}: ${OLD_PORT_CONTAINERS}..."
    docker rm -f ${OLD_PORT_CONTAINERS} || true
fi

# 3. Ensure any container named ml-prediction-engine (running or exited) is completely removed
OLD_NAMED_CONTAINERS=$(docker ps -a --filter "name=^ml-prediction-engine$" -q || true)
if [ -n "$OLD_NAMED_CONTAINERS" ]; then
    echo "Force-removing existing container(s) named ml-prediction-engine: ${OLD_NAMED_CONTAINERS}..."
    docker rm -f ${OLD_NAMED_CONTAINERS} || true
fi

# 4. If a host process is holding the target port, terminate it
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${TARGET_PORT}/tcp" >/dev/null 2>&1 || true
fi

# 5. Clean up any stale network endpoints from previous builds
docker network rm ml-prediction-stack_ml-grid-net >/dev/null 2>&1 || true
docker network rm deploy_ml-grid-net >/dev/null 2>&1 || true

# 6. Verify if TARGET_PORT is free; if not, fallback to alternate port 8008
PORT_IN_USE=false
if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "${TARGET_PORT}" && PORT_IN_USE=true || true
elif command -v curl >/dev/null 2>&1; then
    curl -s --connect-timeout 1 "http://127.0.0.1:${TARGET_PORT}" >/dev/null 2>&1 && PORT_IN_USE=true || true
fi

if [ "$PORT_IN_USE" = true ]; then
    echo "⚠️ Host port ${TARGET_PORT} remains busy by an external service."
    TARGET_PORT="8008"
    echo "Switching active host port to: ${TARGET_PORT}"
fi

export HOST_PORT="${TARGET_PORT}"
echo "${TARGET_PORT}" > "${WORKSPACE_DIR}/.active_port"
echo "Active deployment port set to: ${HOST_PORT}"

# 7. Deploy the stack (Compose or native Docker fallback)
if [ -n "$COMPOSE_CMD" ]; then
    echo "Deploying via ${COMPOSE_CMD} (Project: ${PROJECT_NAME}, Host Port: ${HOST_PORT})..."
    $COMPOSE_CMD -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" up -d
else
    echo "Ensuring Docker volumes and network exist..."
    docker volume create ml_models_data >/dev/null 2>&1 || true
    docker volume create ml_logs_data >/dev/null 2>&1 || true
    docker network create ml-grid-net >/dev/null 2>&1 || true

    echo "Launching container ml-prediction-engine:latest on port ${HOST_PORT}..."
    docker run -d \
        --name ml-prediction-engine \
        --restart unless-stopped \
        -p "${HOST_PORT}:8000" \
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

echo "Waiting for ML Prediction Engine to initialize on http://127.0.0.1:${HOST_PORT}..."
MAX_RETRIES=20
COUNT=0
HEALTHY=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${HOST_PORT}/api/v1/health" || true)
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
echo "✅ DEPLOYMENT SUCCEEDED: Service running on http://127.0.0.1:${HOST_PORT}"
echo "=========================================================="
