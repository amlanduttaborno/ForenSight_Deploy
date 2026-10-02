from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def build_demo_report(path: Path, *, analysis, regions: list[dict]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    page_w, page_h = A4
    y = page_h - 48

    c.setFont("Helvetica-Bold", 18)
    c.drawString(48, y, "ForenSight - Trained Forensic Analysis Report")
    y -= 28
    c.setFont("Helvetica", 9)
    c.drawString(48, y, "TRAINED MULTIMODAL MODEL - results are not a legal determination")
    y -= 30

    fields = [
        ("Analysis ID", analysis.id),
        ("Filename", analysis.filename),
        ("Verdict", analysis.verdict),
        ("Manipulation probability", f"{analysis.preliminary_score:.4f}"),
        ("Highlighted area", f"{analysis.manipulated_area_pct:.2f}%"),
        ("Suspicious regions", str(analysis.region_count)),
        ("Caption provided", "Yes" if analysis.caption else "No"),
        ("SHA-256", analysis.sha256),
        ("Model status", analysis.model_status),
    ]

    c.setFont("Helvetica", 10)
    for key, value in fields:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(48, y, f"{key}:")
        c.setFont("Helvetica", 10)
        text = str(value)
        c.drawString(175, y, text[:90])
        y -= 18

    y -= 10
    overlay = Path(analysis.artifact_dir) / "overlay.jpg"
    if overlay.exists():
        img = ImageReader(str(overlay))
        c.drawImage(img, 48, max(120, y - 270), width=500, height=260, preserveAspectRatio=True, anchor="c")
        y -= 290

    if y < 120:
        c.showPage()
        y = page_h - 48

    c.setFont("Helvetica-Bold", 12)
    c.drawString(48, y, "Regions")
    y -= 20
    c.setFont("Helvetica", 9)
    if not regions:
        c.drawString(48, y, "No connected high-evidence region passed the model size filter.")
    else:
        for r in regions[:8]:
            c.drawString(
                48,
                y,
                f"#{r['index']} bbox=({r['x']},{r['y']},{r['width']},{r['height']}) "
                f"area={r['area_pct']:.3f}% evidence={r['mean_evidence']:.4f}",
            )
            y -= 15

    c.save()
