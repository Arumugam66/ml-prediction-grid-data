"""API route handlers."""
from .health import router as health_router
from .predict import router as predict_router
from .metrics import router as metrics_router
from .train import router as train_router

__all__ = ["health_router", "predict_router", "metrics_router", "train_router"]
