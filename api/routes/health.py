from fastapi import APIRouter
from datetime import datetime
from model_registry.manager import ModelRegistryManager

router = APIRouter()

@router.get("/health", tags=["Health"])
def health_check():
    registry = ModelRegistryManager()
    active_v = registry.get_latest_version() or "None"
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_model_version": active_v,
        "engine": "XGBoost MultiOutput Forecasting Engine"
    }
