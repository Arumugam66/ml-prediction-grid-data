import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class TelemetryCleaner:
    def __init__(self, resample_freq: str = "1h"):
        freq = resample_freq.replace("H", "h")
        if freq.endswith("m") and not freq.endswith("min") and not freq.endswith("ms"):
            freq = freq + "in"
        self.resample_freq = freq

    def clean_and_resample(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resample telemetry per site, compute robust hourly energy deltas."""
        logger.info(f"Cleaning & resampling telemetry data to '{self.resample_freq}' frequency...")

        cleaned_site_dfs = []
        for site_code, group in df.groupby("site_code"):
            site_df = self._clean_single_site(group, site_code)
            if len(site_df) > 0:
                cleaned_site_dfs.append(site_df)

        final_df = pd.concat(cleaned_site_dfs, ignore_index=True)
        final_df = final_df.sort_values(["site_code", "timestamp"]).reset_index(drop=True)
        logger.info(f"Cleaned resampled dataset shape: {final_df.shape}")
        return final_df

    def _clean_single_site(self, group: pd.DataFrame, site_code: str) -> pd.DataFrame:
        group = group.sort_values("timestamp").copy()
        group = group.drop_duplicates(subset=["timestamp"], keep="first")

        # Group into continuous segments if gaps > 6 hours
        group["time_gap_hrs"] = group["timestamp"].diff().dt.total_seconds() / 3600.0
        group["segment_id"] = (group["time_gap_hrs"] > 6.0).cumsum()

        resampled_segments = []

        for seg_id, seg_df in group.groupby("segment_id"):
            if len(seg_df) < 2:
                continue

            seg_df = seg_df.set_index("timestamp")

            agg_rules = {
                "EBKwh": "mean",
                "DGKwh": "mean",
                "TotalKw": "mean",
                "TotalPF": "mean",
                "TotalKVA": "mean",
                "AverageCurrent": "mean",
                "AveragePhasevoltage": "mean",
                "AverageLinevoltage": "mean",
                "Frequency": "mean",
                "EBRunhour": "max",
                "DGRunhour": "max",
            }
            agg_rules = {k: v for k, v in agg_rules.items() if k in seg_df.columns}

            res = seg_df.resample(self.resample_freq).agg(agg_rules)

            # Continuous metric interpolation
            cont_cols = ["TotalKw", "TotalPF", "TotalKVA", "AverageCurrent", "AveragePhasevoltage", "AverageLinevoltage", "Frequency"]
            for col in cont_cols:
                if col in res.columns:
                    res[col] = res[col].interpolate(method="linear").fillna(0.0)

            # Cumulative interpolation
            res["EBKwh"] = res["EBKwh"].interpolate(method="linear").ffill().bfill()
            res["DGKwh"] = res["DGKwh"].interpolate(method="linear").ffill().bfill()

            # Physical energy delta scaled by time interval hours
            freq_hours = pd.Timedelta(self.resample_freq).total_seconds() / 3600.0
            est_delta = (res["TotalKw"].clip(lower=0.0) * freq_hours).round(4)
            
            eb_diff = res["EBKwh"].diff().clip(lower=0.0).fillna(0.0).round(4)
            dg_diff = res["DGKwh"].diff().clip(lower=0.0).fillna(0.0).round(4)

            # Use cumulative meter diff if available and non-zero, otherwise fall back to estimated load delta
            res["EBKwh_delta"] = np.where(eb_diff > 0, eb_diff, est_delta)
            
            # DG consumption only active when generator runhours increase or DG meter advances
            dg_active = (res["DGRunhour"].diff() > 0.0) | (dg_diff > 0.0)
            res["DGKwh_delta"] = np.where(dg_active, np.where(dg_diff > 0, dg_diff, est_delta), 0.0)

            res["site_code"] = site_code
            resampling_reset = res.reset_index()
            resampled_segments.append(resampling_reset)

        if not resampled_segments:
            return pd.DataFrame()

        return pd.concat(resampled_segments, ignore_index=True)
