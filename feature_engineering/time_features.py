import numpy as np
import pandas as pd

class TimeFeatureGenerator:
    """Generates temporal features and cyclical encodings for energy consumption patterns."""

    @staticmethod
    def add_time_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
        df = df.copy()
        ts = pd.to_datetime(df[timestamp_col])

        df["hour"] = ts.dt.hour
        df["day_of_week"] = ts.dt.dayofweek
        df["day_of_month"] = ts.dt.day
        df["month"] = ts.dt.month
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

        # Cyclical features for hour (0-23)
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)

        # Cyclical features for day of week (0-6)
        df["day_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7.0)
        df["day_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7.0)

        return df
