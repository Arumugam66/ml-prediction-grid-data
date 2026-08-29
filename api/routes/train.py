from fastapi import APIRouter, HTTPException, BackgroundTasks
import subprocess
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def run_training_task():
    try:
        logger.info("Triggering run_pipeline.py from API request...")
        subprocess.run(["python", "run_pipeline.py"], check=True)
    except Exception as e:
        logger.error(f"Re-training task failed: {e}")

@router.post("/train", tags=["Training"])
def trigger_training(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(run_training_task)
        return {
            "status": "training_initiated",
            "message": "Pipeline training execution started in background task."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate training: {str(e)}")
