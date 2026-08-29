from fastapi import APIRouter, HTTPException
from model_registry.manager import ModelRegistryManager

router = APIRouter()

@router.get("/metrics", tags=["Metrics"])
def get_model_metrics():
    registry = ModelRegistryManager()
    try:
        _, _, metadata, active_version = registry.load_active_model()
        return {
            "active_version": active_version,
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"No active model metrics available: {str(e)}")
