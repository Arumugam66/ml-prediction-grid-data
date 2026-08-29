import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from model_registry.manager import ModelRegistryManager
from feature_engineering.pipeline import FeaturePipeline

logger = logging.getLogger(__name__)

class EnergyPredictor:
    """Online prediction engine for multi-horizon energy consumption forecasting."""

    def __init__(self, registry_dir: str = "models_artifacts/xgboost"):
        self.registry = ModelRegistryManager(registry_dir)
        self.model = None
        self.feature_list = []
        self.metadata = {}
        self.active_version = ""
        self.reload_model()

    def reload_model(self):
        """Reload active model version from registry."""
        try:
            self.model, self.feature_list, self.metadata, self.active_version = self.registry.load_active_model()
            logger.info(f"Loaded model version '{self.active_version}' with {len(self.feature_list)} features.")
        except Exception as e:
            logger.warning(f"Could not load active model: {e}")

    def predict_future(
        self,
        historical_df: pd.DataFrame,
        site_code: str,
        horizon_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Predict future EBKwh and DGKwh consumption for specified horizon hours."""
        if self.model is None:
            self.reload_model()
            if self.model is None:
                raise RuntimeError("No trained model version available for inference.")

        site_df = historical_df[historical_df["site_code"] == site_code].sort_values("timestamp").copy()
        if len(site_df) < 48:
            raise ValueError(f"Insufficient historical data for site '{site_code}'. Need at least 48 hourly steps.")

        last_timestamp = site_df["timestamp"].max()

        # Handle last cumulative readings safely
        eb_series = site_df["EBKwh"].dropna()
        dg_series = site_df["DGKwh"].dropna()

        last_eb_cum = float(eb_series.iloc[-1]) if len(eb_series) > 0 else 0.0
        last_dg_cum = float(dg_series.iloc[-1]) if len(dg_series) > 0 else 0.0

        current_buffer = site_df.copy()
        predictions = []

        running_eb_cum = last_eb_cum
        running_dg_cum = last_dg_cum

        # Load config for resample frequency
        resample_freq = "30m"
        try:
            import yaml
            with open("config/config.yaml", "r") as f:
                cfg = yaml.safe_load(f)
                resample_freq = cfg.get("data", {}).get("resample_freq", "30m")
        except Exception:
            pass

        freq_td = pd.Timedelta(resample_freq)
        steps_per_hour = max(1, int(round(pd.Timedelta("1h") / freq_td)))
        total_steps = horizon_hours * steps_per_hour

        for step in range(1, total_steps + 1):
            next_ts = last_timestamp + step * freq_td

            pipeline = FeaturePipeline()
            df_feat, feature_cols = pipeline.fit_transform(current_buffer)

            row_feat = pd.DataFrame(index=[0])
            for col in self.feature_list:
                if col in df_feat.columns:
                    val = df_feat[col].iloc[-1]
                    row_feat[col] = float(val) if pd.notna(val) else 0.0
                elif col.startswith("site_"):
                    curr_site_col = f"site_{site_code}"
                    row_feat[col] = 1.0 if col == curr_site_col else 0.0
                else:
                    row_feat[col] = 0.0

            X_pred = row_feat[self.feature_list].values
            pred_deltas = self.model.predict(X_pred)[0]

            eb_delta = float(max(0.0, pred_deltas[0]))
            dg_delta = float(max(0.0, pred_deltas[1]))

            running_eb_cum += eb_delta
            running_dg_cum += dg_delta

            pred_record = {
                "step": step,
                "timestamp": next_ts.isoformat(),
                "site_code": site_code,
                "predicted_EBKwh_delta": round(eb_delta, 3),
                "predicted_DGKwh_delta": round(dg_delta, 3),
                "predicted_EBKwh_cumulative": round(running_eb_cum, 3),
                "predicted_DGKwh_cumulative": round(running_dg_cum, 3)
            }
            predictions.append(pred_record)

            # Update buffer for multi-step autoregressive features
            new_row = {
                "timestamp": next_ts,
                "site_code": site_code,
                "EBKwh": running_eb_cum,
                "DGKwh": running_dg_cum,
                "EBKwh_delta": eb_delta,
                "DGKwh_delta": dg_delta,
                "TotalKw": float(current_buffer["TotalKw"].iloc[-1]) if pd.notna(current_buffer["TotalKw"].iloc[-1]) else 0.0,
                "TotalPF": float(current_buffer["TotalPF"].iloc[-1]) if pd.notna(current_buffer["TotalPF"].iloc[-1]) else 0.95,
                "TotalKVA": float(current_buffer["TotalKVA"].iloc[-1]) if pd.notna(current_buffer["TotalKVA"].iloc[-1]) else 0.0,
                "AverageCurrent": float(current_buffer["AverageCurrent"].iloc[-1]) if pd.notna(current_buffer["AverageCurrent"].iloc[-1]) else 0.0,
                "AveragePhasevoltage": float(current_buffer["AveragePhasevoltage"].iloc[-1]) if pd.notna(current_buffer["AveragePhasevoltage"].iloc[-1]) else 230.0,
                "AverageLinevoltage": float(current_buffer["AverageLinevoltage"].iloc[-1]) if pd.notna(current_buffer["AverageLinevoltage"].iloc[-1]) else 400.0,
                "Frequency": 50.0,
                "EBRunhour": float(current_buffer["EBRunhour"].iloc[-1]) if pd.notna(current_buffer["EBRunhour"].iloc[-1]) else 0.0,
                "DGRunhour": float(current_buffer["DGRunhour"].iloc[-1]) if pd.notna(current_buffer["DGRunhour"].iloc[-1]) else 0.0
            }
            current_buffer = pd.concat([current_buffer, pd.DataFrame([new_row])], ignore_index=True)

        return predictions
