"""Read-only access to evaluation artifacts exported by ForenSight_Final.ipynb."""
import csv
import json
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, HTTPException

from ..config import settings

router = APIRouter(prefix="/research", tags=["research"])
CHECKPOINTS = Path(settings.model_checkpoint).resolve().parent


def read_csv(name: str) -> List[Dict[str, str]]:
    path = CHECKPOINTS / name
    if not path.exists():
        raise HTTPException(404, "Notebook artifact is missing: " + name)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@router.get("/status")
def status():
    """Compatibility endpoint for the existing research page."""
    return {
        "project": "ForenSight — Explainable Multimodal Image Forensics",
        "current_stage": "Trained AutoSplice checkpoint integrated and evaluated",
        "completed": [
            "Trained classification", "Pixel localization", "Notebook evaluation export",
            "Single and batch image workflows", "Interactive localization and Grad-CAM tools",
            "History search, comparison, duplicate lookup, cases, and review reporting",
        ],
        "pending": ["External-domain validation and retraining for arbitrary image sources"],
        "demo_message": "The application loads best.pt; displayed research metrics come from the notebook exports.",
    }


@router.get("/evaluation")
def evaluation():
    metrics_path = CHECKPOINTS / "test_metrics.json"
    config_path = CHECKPOINTS / "run_config.json"
    if not metrics_path.exists() or not config_path.exists():
        raise HTTPException(404, "Notebook metrics/config output is missing")
    return {
        "source": "ForenSight_Final.ipynb exported notebook artifacts",
        "metrics": json.loads(metrics_path.read_text(encoding="utf-8")),
        "run_config": json.loads(config_path.read_text(encoding="utf-8")),
        "compression": read_csv("jpeg_robustness.csv"),
        "ablation": read_csv("text_modality_ablation.csv"),
        "training": read_csv("training_history.csv"),
    }
