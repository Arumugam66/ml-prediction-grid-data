from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import logging

from data_preparation.loader import TelemetryLoader
from data_preparation.cleaner import TelemetryCleaner
from serving.predictor import EnergyPredictor

logger = logging.getLogger(__name__)
router = APIRouter()

# Global cached predictor & cleaned dataframe
predictor = EnergyPredictor()
_cached_cleaned_df: Optional[pd.DataFrame] = None

def get_cleaned_data() -> pd.DataFrame:
    global _cached_cleaned_df
    if _cached_cleaned_df is None:
        logger.info("Loading and caching cleaned telemetry dataset for serving...")
        import yaml
        resample_freq = "30m"
        raw_path = "grid_data.parquet"
        try:
            with open("config/config.yaml", "r") as f:
                cfg = yaml.safe_load(f)
                resample_freq = cfg.get("data", {}).get("resample_freq", "30m")
                raw_path = cfg.get("data", {}).get("raw_file_path", "grid_data.parquet")
        except Exception:
            pass

        loader = TelemetryLoader(raw_path)
        raw_df = loader.load_raw_data()
        cleaner = TelemetryCleaner(resample_freq)
        _cached_cleaned_df = cleaner.clean_and_resample(raw_df)
    return _cached_cleaned_df

class ForecastRequest(BaseModel):
    site_code: str = "RAMS002"
    horizon_hours: int = 24

@router.get("/sites", tags=["Sites"])
def get_available_sites():
    try:
        cleaned_df = get_cleaned_data()
        sites = cleaned_df["site_code"].unique().tolist()
        return {"sites": sites}
    except Exception as e:
        return {"sites": ["RAMS001", "RAMS002", "EMS000182"]}

@router.post("/predict", tags=["Prediction"])
def predict_energy(req: ForecastRequest):
    try:
        cleaned_df = get_cleaned_data()

        if req.site_code not in cleaned_df["site_code"].values:
            raise HTTPException(status_code=400, detail=f"Site code '{req.site_code}' not found in telemetry dataset.")

        predictions = predictor.predict_future(
            historical_df=cleaned_df,
            site_code=req.site_code,
            horizon_hours=req.horizon_hours
        )

        return {
            "status": "success",
            "active_model_version": predictor.active_version,
            "site_code": req.site_code,
            "horizon_hours": req.horizon_hours,
            "forecast": predictions
        }
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")
