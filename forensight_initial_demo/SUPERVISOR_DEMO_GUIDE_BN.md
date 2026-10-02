# কালকের Supervisor Demo — 10 মিনিটের সহজ Script

## Demo শুরু করার আগে

দুইটা terminal খোলা রাখুন:

### Terminal 1 — Backend

```powershell
cd forensight_initial_demo\backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

### Terminal 2 — Frontend

```powershell
cd forensight_initial_demo\frontend
npm run dev
```

Browser:

`http://localhost:3000`

---

## 1. Dashboard দেখান

বলুন:

> "আমরা শুধু classifier বানাচ্ছি না; final system-এ image authenticity, localization, forensic evidence এবং multimodal image-text analysis একই application-এ থাকবে।"

Dashboard-এর architecture cards দেখান।

---

## 2. Research page দেখান

বলুন:

> "আমাদের ML training pipeline, CLIP branch, forensic branch, segmentation এবং checkpoint workflow implement করা হয়েছে। Dataset audit-এ AutoSplice-এর source-ID mapping issue identify করেছি। তাই final metric claim করার আগে mapping correction এবং aligned multimodal retraining করছি।"

এটি research integrity দেখাবে।

---

## 3. Analyze page

একটা JPG/PNG upload করুন।

Caption দিন, যেমন:

```text
A man standing beside a red car on a city street.
```

বলুন:

> "Final app-এর multimodal contract হলো image + optional accompanying text. Final checkpoint connect হওয়ার পর এই text CLIP text encoder-এ যাবে।"

`Run preliminary analysis` চাপুন।

---

## 4. Result dashboard

দেখান:

- Preliminary Evidence Score
- Highlighted Area
- Region Count
- Original
- Overlay
- Mask
- Heatmap
- Caption section

স্পষ্ট বলুন:

> "এই মুহূর্তের score final trained AI probability নয়; এটি UI/backend workflow prove করার জন্য preliminary forensic visualization. Final AutoSplice-aligned checkpoint retrain হওয়ার পর একই result contract-এ real classification এবং localization output আসবে।"

---

## 5. PDF report

`PDF report` চাপুন।

বলুন final version-এ report-এ থাকবে:

- model version
- authenticity probability
- localization mask
- suspicious regions
- image-text analysis
- image hash
- limitations

---

## 6. History

History page দেখিয়ে বলুন analysis result backend database-এ save হচ্ছে।

---

# Supervisor যদি জিজ্ঞেস করেন “Final model কোথায়?”

বলুন:

> "The architecture and training pipeline are implemented. Our first run exposed an AutoSplice-specific mapping mismatch between authentic/forged filenames, masks and individual caption JSON files. We deliberately did not present those preliminary metrics as final. We are correcting the source-ID manifest, then we will retrain the aligned image-text-mask model and replace this demo engine with the validated best.pt checkpoint."

---

# Supervisor যদি জিজ্ঞেস করেন “Multimodal কোথায়?”

বলুন:

> "The final architecture contains CLIP image and text encoders. The app already accepts image and accompanying text as separate modalities. In the current supervisor build the interface and API contract are active, while the final trained fusion checkpoint is pending the corrected AutoSplice alignment."

---

# কী বলা যাবে না

এখন বলবেন না:

- "আমাদের final accuracy 91%"
- "এই app সত্যিই image fake প্রমাণ করে"
- "এই mask final AI mask"

বরং বলবেন:

- preliminary pipeline
- prototype
- UI/backend integration
- final checkpoint pending
- aligned retraining next

