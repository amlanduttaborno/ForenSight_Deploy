"""Clearly-labelled preliminary demo inference.

This module exists only so the supervisor demo can prove the complete
frontend/backend/artifact workflow before the corrected AutoSplice-trained
checkpoint is connected. The returned score is NOT a trained authenticity
probability.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


@dataclass
class DemoResult:
    verdict: str
    preliminary_score: float
    manipulated_area_pct: float
    regions: list[dict]
    width: int
    height: int


class DemoInferenceEngine:
    model_status = "PRELIMINARY DEMO ENGINE — FINAL MULTIMODAL CHECKPOINT NOT CONNECTED"

    def analyze(self, image_bytes: bytes, output_dir: Path) -> DemoResult:
        pil = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = pil.size
        rgb = np.asarray(pil)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # High-frequency residual + edge evidence. This is deliberately a
        # visualization heuristic, not a learned forensic classifier.
        blur = cv2.GaussianBlur(gray, (0, 0), 2.0)
        residual = cv2.absdiff(gray, blur).astype(np.float32)
        lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))

        def norm(x: np.ndarray) -> np.ndarray:
            maximum = float(x.max())
            if maximum <= 1e-8:
                return np.zeros_like(x, dtype=np.float32)
            return (x / maximum).astype(np.float32)

        evidence = 0.55 * norm(residual) + 0.45 * norm(lap)
        evidence_u8 = np.clip(evidence * 255, 0, 255).astype(np.uint8)

        # Keep only the strongest local evidence so the mask is easy to inspect.
        threshold = max(35, int(np.percentile(evidence_u8, 92)))
        mask = (evidence_u8 >= threshold).astype(np.uint8) * 255
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Connected components -> suspicious regions.
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        total_pixels = max(1, width * height)
        min_area = max(20, int(total_pixels * 0.0006))
        components: list[tuple[int, int, int, int, int, float]] = []
        cleaned = np.zeros_like(mask)

        for label in range(1, count):
            x, y, w, h, area = [int(v) for v in stats[label]]
            if area < min_area:
                continue
            component_mask = labels == label
            cleaned[component_mask] = 255
            mean_evidence = float(evidence[component_mask].mean()) if component_mask.any() else 0.0
            components.append((x, y, w, h, area, mean_evidence))

        components.sort(key=lambda item: item[4], reverse=True)
        components = components[:8]

        regions = []
        for idx, (x, y, w, h, area, mean_evidence) in enumerate(components, start=1):
            regions.append({
                "index": idx,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "area_pct": round(area / total_pixels * 100, 3),
                "mean_evidence": round(mean_evidence, 4),
            })

        manipulated_area_pct = round(float((cleaned > 0).sum()) / total_pixels * 100, 2)

        # Evidence score is only a display heuristic. Use upper-tail evidence so
        # the number remains stable across different image sizes.
        flat = evidence.reshape(-1)
        if flat.size:
            cutoff = np.quantile(flat, 0.95)
            upper = flat[flat >= cutoff]
            score = float(np.clip(upper.mean() if upper.size else flat.mean(), 0, 1))
        else:
            score = 0.0

        if score >= 0.58:
            verdict = "HIGH PRELIMINARY FORENSIC EVIDENCE"
        elif score >= 0.40:
            verdict = "MODERATE PRELIMINARY FORENSIC EVIDENCE"
        else:
            verdict = "LOW PRELIMINARY FORENSIC EVIDENCE"

        output_dir.mkdir(parents=True, exist_ok=True)
        pil.save(output_dir / "original.jpg", quality=95)
        Image.fromarray(cleaned).save(output_dir / "mask.png")

        heat = cv2.applyColorMap(evidence_u8, cv2.COLORMAP_JET)
        cv2.imwrite(str(output_dir / "heatmap.png"), heat)

        overlay = bgr.copy()
        red_layer = np.zeros_like(overlay)
        red_layer[:, :, 2] = 255
        alpha = 0.42
        region_pixels = cleaned > 0
        overlay[region_pixels] = cv2.addWeighted(
            overlay, 1 - alpha, red_layer, alpha, 0
        )[region_pixels]
        for r in regions:
            cv2.rectangle(
                overlay,
                (r["x"], r["y"]),
                (r["x"] + r["width"], r["y"] + r["height"]),
                (0, 215, 255),
                2,
            )
        cv2.imwrite(str(output_dir / "overlay.jpg"), overlay)

        return DemoResult(
            verdict=verdict,
            preliminary_score=round(score, 4),
            manipulated_area_pct=manipulated_area_pct,
            regions=regions,
            width=width,
            height=height,
        )
