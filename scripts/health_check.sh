#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "  RUNNING POST-DEPLOYMENT SMOKE & HEALTH TESTS"
echo "=========================================================="

WORKSPACE_DIR="$(pwd)"
ACTIVE_PORT="8000"
if [ -f "${WORKSPACE_DIR}/.active_port" ]; then
    ACTIVE_PORT=$(cat "${WORKSPACE_DIR}/.active_port")
fi
PORT="${ACTIVE_PORT:-${APP_PORT:-8000}}"
BASE_URL="${1:-http://127.0.0.1:${PORT}}"
ERRORS=0

test_endpoint() {
    local name="$1"
    local path="$2"
    local expected_code="$3"
    
    echo -n "Testing ${name} (${BASE_URL}${path})... "
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}${path}" || true)
    
    if [ "$HTTP_CODE" = "$expected_code" ]; then
        echo "✅ OK (HTTP $HTTP_CODE)"
    else
        echo "❌ FAIL (Expected $expected_code, Got $HTTP_CODE)"
        ERRORS=$((ERRORS + 1))
    fi
}

# 1. API Health
test_endpoint "API Health Check" "/api/v1/health" "200"

# 2. Available Sites
test_endpoint "Sites Listing" "/api/v1/sites" "200"

# 3. Model Performance Metrics
test_endpoint "Model Metrics" "/api/v1/metrics" "200"

# 4. Interactive Swagger Documentation
test_endpoint "FastAPI Swagger Docs" "/docs" "200"

# 5. Genset Monitoring Dashboard
test_endpoint "Genset Frontend Dashboard" "/" "200"

echo "=========================================================="
if [ $ERRORS -eq 0 ]; then
    echo "🎉 ALL SMOKE TESTS PASSED! System is fully operational."
    exit 0
else
    echo "❌ $ERRORS TEST(S) FAILED. Verification failed."
    exit 1
fi
