import ast
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class TelemetryLoader:
    def __init__(self, file_path: str = "grid_data.parquet"):
        self.file_path = file_path

    def load_raw_data(self) -> pd.DataFrame:
        """Load parquet telemetry data and unpack nested metric_json."""
        logger.info(f"Loading parquet dataset from {self.file_path}...")
        df = pd.read_parquet(self.file_path)

        if "metric_json" not in df.columns:
            raise ValueError("Dataset missing required 'metric_json' column.")

        df["timestamp"] = pd.to_datetime(df["received_on"])
        df["site_code"] = df["site_code"].astype(str).str.strip()
        df["slave_id"] = df["slave_id"].astype(str).str.strip() if "slave_id" in df.columns else "1"

        parsed_records = []
        for idx, row in df.iterrows():
            metric_str = row["metric_json"]
            parsed_dict = self._parse_json_field(metric_str)
            parsed_records.append(parsed_dict)

        metrics_df = pd.DataFrame(parsed_records)

        meta_cols = [c for c in ["id", "site_code", "slave_id", "timestamp"] if c in df.columns]
        combined_df = pd.concat([
            df[meta_cols].reset_index(drop=True),
            metrics_df.reset_index(drop=True)
        ], axis=1)

        numeric_cols = [
            "EBKwh", "DGKwh", "TotalKw", "TotalPF", "TotalKVA",
            "AverageCurrent", "AveragePhasevoltage", "AverageLinevoltage",
            "Frequency", "EBRunhour", "DGRunhour"
        ]

        for col in numeric_cols:
            if col in combined_df.columns:
                combined_df[col] = pd.to_numeric(combined_df[col], errors="coerce")
            else:
                combined_df[col] = 0.0

        combined_df = combined_df.sort_values(["site_code", "slave_id", "timestamp"]).reset_index(drop=True)
        logger.info(f"Successfully loaded {len(combined_df)} records across sites: {combined_df['site_code'].unique().tolist()}")
        return combined_df

    @staticmethod
    def _parse_json_field(val: str) -> dict:
        if not val or not isinstance(val, str):
            return {}
        try:
            return json.loads(val)
        except Exception:
            try:
                return ast.literal_eval(val)
            except Exception:
                return {}
