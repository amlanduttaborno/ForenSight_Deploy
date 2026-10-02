# ForenSight

ForenSight is a FastAPI + Next.js image-forensics application. It loads the supplied trained `backend/checkpoints/best.pt` multimodal checkpoint for classification and pixel-level localization. It is a research tool: its results are model predictions, not legal determinations.

## What is included

- JPG, PNG, and WEBP upload with an optional caption.
- Trained-model verdict, probability, mask, heatmap, overlay, probability map, suspicious regions, Grad-CAM, metadata, and PDF report.
- SQLite persistence for images/results, private signed-in history, comparison, investigation cases, and account deletion requests.
- Registration/login, 1,000 initial tokens, 10-token completed verification deduction, token ledger, referral reward, profile name/avatar, notifications, preferences, dark/light theme, and English/Bangla navigation and key account/help workflows.
- FAQ and authenticated feedback/issue reporting.
- Administrator analytics, user enable/disable and audited token adjustment, verification review, feedback/deletion queues, announcements, and system settings.
- Notebook-evaluation dashboard reading the exported metrics next to `best.pt`.

Payment gateway code and payment UI are intentionally not included.

## Run locally on Windows

Open **Terminal 1** in `forensight_initial_demo\backend`:

```powershell
.\.venv-trained\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **Terminal 2** in `forensight_initial_demo\frontend`:

```powershell
npm.cmd run dev -- --hostname 127.0.0.1
```

Then open [http://localhost:3000](http://localhost:3000). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

## Administrator setup

Set a strong, private `ADMIN_PASSWORD` in `backend/.env`, before starting the backend for the first time with that email:

```env
ADMIN_EMAIL=admin@forensight.local
ADMIN_PASSWORD=replace-with-a-long-unique-password
```

Restart the backend, then sign in at **`/admin/login`** with that email/password. User sign-in at **Account** rejects administrator accounts, and the administrator dashboard at **`/admin`** redirects non-administrators to the separate sign-in page. Never commit a real administrator password to source control.

## Verification flow

1. Register or log in through **Account**. New users receive 1,000 tokens; authentication is mandatory before an image can be analyzed.
2. Open **Analyze**, choose one image or a batch of up to eight images, optionally add a caption, and run the trained analysis. On success, 10 tokens are deducted per completed image and a result notification is created.
3. Inspect the original, overlay, mask, heatmap, raw probability map, threshold explorer, regions, optional Grad-CAM, and PDF report.
4. Use **History** or save results into **Cases**.

The **Research** route displays the metrics exported by `ForenSight_Final.ipynb`, including source-balanced classification results, localization Dice/IoU, JPEG robustness, and the text-modality ablation. Those metrics describe the notebook evaluation data; they do not guarantee identical accuracy for every external image.
