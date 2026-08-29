import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Include parent directory in sys.path
sys.path.insert(0, os.path.abspath("."))

from api.routes import health_router, predict_router, metrics_router, train_router

app = FastAPI(
    title="Energy Consumption Forecasting ML Engine",
    description="XGBoost multi-target prediction server for EBKwh (Grid) and DGKwh (Generator) energy usage.",
    version="1.0.0"
)

# Enable CORS for frontend dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Router Modules
app.include_router(health_router, prefix="/api/v1")
app.include_router(predict_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(train_router, prefix="/api/v1")

@app.get("/")
def root():
    # Return HTML dashboard if available
    dashboard_path = os.path.abspath("genset-dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Energy Consumption Forecasting ML API is online. Visit /docs for Swagger UI."}

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
