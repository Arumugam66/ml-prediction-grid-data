#!/usr/bin/env python3
"""
Automated Test Runner for Energy Consumption Forecasting ML Engine
Validates configurations, data loader, feature engineering, model registry, and FastAPI routes.
"""

import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.abspath(".") not in sys.path:
    sys.path.insert(0, os.path.abspath("."))

import yaml
import traceback

def log_test(name, passed, msg=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{status}] {name} {f'({msg})' if msg else ''}")

def run_tests():
    print("=" * 60)
    print("  RUNNING ML PREDICTION ENGINE CI/CD TEST SUITE")
    print("=" * 60)
    
    failures = 0

    # 1. Configuration Validation
    try:
        config_path = os.path.join(REPO_ROOT, "config", "config.yaml")
        model_config_path = os.path.join(REPO_ROOT, "config", "model_config.yaml")
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        assert "data" in cfg and "raw_file_path" in cfg["data"]
        assert "pipeline" in cfg
        assert "quality_gate" in cfg
        with open(model_config_path, "r") as f:
            m_cfg = yaml.safe_load(f)
        assert "xgboost" in m_cfg and "features" in m_cfg
        log_test("Configuration File Schemas", True)
    except Exception as e:
        log_test("Configuration File Schemas", False, str(e))
        failures += 1

    # 2. Module Import Verification
    modules = [
        "data_preparation.loader",
        "data_preparation.cleaner",
        "feature_engineering.pipeline",
        "feature_engineering.lag_features",
        "feature_engineering.time_features",
        "quality_gate.evaluator",
        "model_registry.manager",
        "serving.predictor",
        "api.main"
    ]
    for mod in modules:
        try:
            __import__(mod)
            log_test(f"Import: {mod}", True)
        except Exception as e:
            log_test(f"Import: {mod}", False, str(e))
            failures += 1

    # 3. Model Registry Integrity Check
    try:
        from model_registry.manager import ModelRegistryManager
        mgr = ModelRegistryManager()
        latest_v = mgr.get_latest_version()
        if latest_v:
            log_test(f"Model Registry Active Version ({latest_v})", True)
        else:
            log_test("Model Registry Active Version", False, "No active model registered in latest.json")
            failures += 1
    except Exception as e:
        log_test("Model Registry Check", False, str(e))
        failures += 1

    # 4. Data Loader Validation
    try:
        from data_preparation.loader import TelemetryLoader
        raw_path = os.path.join(REPO_ROOT, "grid_data.parquet")
        if os.path.exists(raw_path):
            loader = TelemetryLoader(raw_path)
            raw_df = loader.load_raw_data()
            assert not raw_df.empty, "Dataframe is empty"
            log_test(f"Telemetry Loader ({raw_path}: {len(raw_df)} rows)", True)
        else:
            log_test("Telemetry Loader Check", False, f"File {raw_path} not found")
            failures += 1
    except Exception as e:
        log_test("Telemetry Loader Check", False, str(e))
        failures += 1

    # 5. FastAPI App & Routes Test
    try:
        from api.main import app

        # Collect all endpoint paths via OpenAPI schema and safe route attribute checks
        registered_paths = set(app.openapi().get("paths", {}).keys())
        for r in getattr(app, "routes", []):
            if hasattr(r, "path"):
                registered_paths.add(r.path)

        expected_routes = [
            "/api/v1/health",
            "/api/v1/predict",
            "/api/v1/metrics",
            "/api/v1/train",
            "/"
        ]
        for route in expected_routes:
            assert route in registered_paths, f"Route '{route}' not found in registered paths: {registered_paths}"

        log_test(f"FastAPI Route Registration ({len(registered_paths)} endpoints registered)", True)
    except Exception as e:
        log_test("FastAPI Route Registration", False, str(e))
        failures += 1

    print("=" * 60)
    if failures == 0:
        print("🎉 ALL TESTS PASSED SUCCESSFULLY! Ready for deployment.")
        sys.exit(0)
    else:
        print(f"❌ {failures} TEST(S) FAILED. Aborting deployment.")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
