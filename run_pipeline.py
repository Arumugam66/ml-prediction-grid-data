import os
import sys
import yaml
import logging
import pandas as pd
from xgboost import XGBRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split

from data_preparation.loader import TelemetryLoader
from data_preparation.cleaner import TelemetryCleaner
from feature_engineering.pipeline import FeaturePipeline
from quality_gate.evaluator import QualityGateEvaluator
from model_registry.manager import ModelRegistryManager

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("run_pipeline")

def load_config():
    with open("config/config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    with open("config/model_config.yaml", "r") as f:
        m_cfg = yaml.safe_load(f)
    return cfg, m_cfg

def main():
    logger.info("==================================================")
    logger.info("  STARTING SINGLE MODEL ML PREDICTION PIPELINE")
    logger.info("==================================================")

    # 1. Load Configurations
    config, model_config = load_config()
    raw_data_path = config["data"]["raw_file_path"]

    # 2. Data Loading
    loader = TelemetryLoader(raw_data_path)
    raw_df = loader.load_raw_data()

    # 3. Data Resampling & Delta Calculation
    cleaner = TelemetryCleaner(resample_freq=config["data"]["resample_freq"])
    cleaned_df = cleaner.clean_and_resample(raw_df)

    # 4. Feature Engineering
    pipeline = FeaturePipeline(
        lag_spans=model_config["features"]["lag_spans"],
        rolling_windows=model_config["features"]["rolling_windows"]
    )
    df_features, feature_cols = pipeline.fit_transform(cleaned_df, target_cols=config["data"]["target_cols"])

    # 5. Train / Validation Split (Time Series Split order preserved)
    target_cols = config["data"]["target_cols"]
    X = df_features[feature_cols].values
    y = df_features[target_cols].values

    test_ratio = config["pipeline"]["test_size"]
    split_idx = int(len(X) * (1 - test_ratio))

    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    logger.info(f"Dataset split: Train={X_train.shape[0]} rows, Validation={X_val.shape[0]} rows across {X_train.shape[1]} features.")

    # 6. Model Training (Unified Multi-Output XGBoost)
    xgb_params = model_config["xgboost"]
    base_xgb = XGBRegressor(**xgb_params)
    unified_model = MultiOutputRegressor(base_xgb)

    logger.info("Training unified MultiOutput XGBoost model...")
    unified_model.fit(X_train, y_train)

    # 7. Validation & Quality Gate Evaluation
    y_pred_val = unified_model.predict(X_val)

    qgate_cfg = config["quality_gate"]
    evaluator = QualityGateEvaluator(
        min_r2=qgate_cfg["min_r2"],
        max_rmse=qgate_cfg["max_rmse"],
        max_mape=qgate_cfg["max_mape"]
    )
    passed, summary = evaluator.evaluate(y_val, y_pred_val, target_names=target_cols)

    logger.info(f"Quality Gate Status: {'PASSED' if passed else 'FAILED (Saved with Warning)'}")

    # 8. Model Registration & Artifact Export
    registry = ModelRegistryManager(base_dir=config["registry"]["artifacts_dir"])

    metadata = {
        "dataset_records": len(df_features),
        "train_records": len(X_train),
        "val_records": len(X_val),
        "feature_count": len(feature_cols),
        "targets": target_cols,
        "quality_gate_summary": summary,
        "hyperparameters": xgb_params
    }

    version_name = registry.register_model_version(
        model_obj=unified_model,
        feature_list=feature_cols,
        metadata=metadata
    )

    logger.info("==================================================")
    logger.info(f"  SUCCESSFULLY REGISTERED UNIFIED MODEL ARTIFACT: {version_name}")
    logger.info(f"  Artifact Directory: {os.path.abspath(config['registry']['artifacts_dir'])}/{version_name}")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
