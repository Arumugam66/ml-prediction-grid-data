import logging
import pandas as pd
from typing import Tuple, List, Dict
from .time_features import TimeFeatureGenerator
from .lag_features import LagFeatureGenerator

logger = logging.getLogger(__name__)

class FeaturePipeline:
    """Orchestrates time-series feature generation for energy forecasting."""

    def __init__(self, lag_spans: List[int] = None, rolling_windows: List[int] = None):
        self.time_gen = TimeFeatureGenerator()
        self.lag_gen = LagFeatureGenerator(lag_spans=lag_spans, rolling_windows=rolling_windows)

    def fit_transform(
        self,
        cleaned_df: pd.DataFrame,
        target_cols: List[str] = None
    ) -> Tuple[pd.DataFrame, List[str]]:
        if target_cols is None:
            target_cols = ["EBKwh_delta", "DGKwh_delta"]

        logger.info("Executing feature engineering pipeline...")
        df = self.time_gen.add_time_features(cleaned_df)
        df = self.lag_gen.add_lag_and_rolling_features(df, target_cols=target_cols)

        # One-hot encode site_code
        site_dummies = pd.get_dummies(df["site_code"], prefix="site", dtype=float)
        df = pd.concat([df, site_dummies], axis=1)

        # Identify feature columns
        exclude_cols = ["id", "timestamp", "site_code", "metric_json"] + target_cols
        feature_cols = [c for c in df.columns if c not in exclude_cols]

        # Drop initial NaN rows created by lag calculations
        max_lag = max(self.lag_gen.lag_spans)
        df_clean = df.dropna(subset=[f"{target_cols[0]}_lag_{max_lag}"]).reset_index(drop=True)

        # Fill remaining feature NaNs with 0
        df_clean[feature_cols] = df_clean[feature_cols].fillna(0.0)

        logger.info(f"Generated {len(feature_cols)} features for {len(df_clean)} records.")
        return df_clean, feature_cols
