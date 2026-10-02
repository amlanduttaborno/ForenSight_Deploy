from pathlib import Path
from uuid import uuid4

from ..config import settings


def create_analysis_dir() -> tuple[str, Path]:
    analysis_id = str(uuid4())
    path = settings.storage_path / analysis_id
    path.mkdir(parents=True, exist_ok=True)
    return analysis_id, path


def safe_artifact_path(analysis_dir: Path, name: str) -> Path:
    allowed = {"original.jpg", "overlay.jpg", "mask.png", "heatmap.png", "probability_map.png", "probability_map.npy", "gradcam.jpg", "report.pdf"}
    if name not in allowed:
        raise ValueError("Unsupported artifact")
    return analysis_dir / name
