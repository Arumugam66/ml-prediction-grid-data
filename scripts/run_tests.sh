#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "=========================================================="
echo "  INITIATING ML PREDICTION CI/CD TEST SUITE"
echo "=========================================================="

# Check if current Python has required dependencies (e.g. inside container or configured host venv)
if python3 -c "import sklearn, uvicorn, pyarrow" >/dev/null 2>&1; then
    echo "✅ Suitable Python environment detected. Running tests directly..."
    python3 scripts/run_all_tests.py
elif command -v docker >/dev/null 2>&1; then
    echo "⚠️  Host Python lacks dependencies (sklearn, uvicorn, pyarrow)."
    echo "🐳 Building Docker image and running test suite inside container environment..."
    docker build -t ml-prediction-engine:latest -f Dockerfile .
    docker run --rm ml-prediction-engine:latest python scripts/run_all_tests.py
else
    echo "⚠️  Docker unavailable. Initializing local virtual environment..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install --no-cache-dir -r requirements.txt
    python scripts/run_all_tests.py
fi
