import logging
import pandas as pd
from typing import List

logger = logging.getLogger(__name__)

class LagFeatureGenerator:
    """Generates lag and rolling window features per site for time-series forecasting."""

    def __init__(self, lag_spans: List[int] = None, rolling_windows: List[int] = None):
        self.lag_spans = lag_spans or [1, 2, 3, 24, 48]
        self.rolling_windows = rolling_windows or [3, 6, 24]

    def add_lag_and_rolling_features(
        self,
        df: pd.DataFrame,
        target_cols: List[str] = None
    ) -> pd.DataFrame:
        if target_cols is None:
            target_cols = ["EBKwh_delta", "DGKwh_delta"]

        df = df.copy()
        processed_site_dfs = []

        for site_code, group in df.groupby("site_code"):
            group = group.sort_values("timestamp").copy()

            for col in target_cols:
                if col not in group.columns:
                    continue

                # Lag features
                for lag in self.lag_spans:
                    group[f"{col}_lag_{lag}"] = group[col].shift(lag)

                # Rolling window features
                for window in self.rolling_windows:
                    group[f"{col}_roll_mean_{window}h"] = group[col].shift(1).rolling(window=window, min_periods=1).mean()
                    group[f"{col}_roll_std_{window}h"] = group[col].shift(1).rolling(window=window, min_periods=1).std().fillna(0.0)
                    group[f"{col}_roll_max_{window}h"] = group[col].shift(1).rolling(window=window, min_periods=1).max()

            processed_site_dfs.append(group)

        result_df = pd.concat(processed_site_dfs, ignore_index=True)
        return result_df
