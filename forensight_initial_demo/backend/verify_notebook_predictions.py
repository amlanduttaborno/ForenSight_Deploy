"""Compare backend inference with probabilities saved by ForenSight_Final.ipynb."""

import csv
from pathlib import Path, PureWindowsPath

import torch
from PIL import Image

from app.services.trained_inference import TrainedInferenceEngine


BACKEND_ROOT = Path(__file__).resolve().parent
VALIDATION_ROOT = BACKEND_ROOT / "validation_data"
PREDICTIONS = BACKEND_ROOT / "checkpoints" / "test_predictions.csv"
CHECKPOINT = BACKEND_ROOT / "checkpoints" / "best.pt"
SAMPLE_IDS = [
    "auth_000008",
    "auth_000009",
    "forged_q100_002291",
    "forged_q100_002292",
]


def main() -> None:
    with PREDICTIONS.open(encoding="utf-8", newline="") as handle:
        rows = {row["sample_id"]: row for row in csv.DictReader(handle)}

    engine = TrainedInferenceEngine(CHECKPOINT, "auto")
    for sample_id in SAMPLE_IDS:
        row = rows[sample_id]
        source = PureWindowsPath(row["image_path"])
        image_path = VALIDATION_ROOT / source.parts[-2] / source.name
        image = Image.open(image_path).convert("RGB")
        inputs = engine._inputs(image, row["caption"])
        with torch.inference_mode():
            output = engine.model(*inputs[:-1])
            actual = float(
                torch.sigmoid(
                    output["manipulation_logit"].float() / engine.temperature
                )[0].cpu()
            )
        expected = float(row["prob"])
        print(
            f"{sample_id} label={row['label']} expected={expected:.6f} "
            f"app={actual:.6f} difference={abs(actual - expected):.6f}"
        )


if __name__ == "__main__":
    main()
