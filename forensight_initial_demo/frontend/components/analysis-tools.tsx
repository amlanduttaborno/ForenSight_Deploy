"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Crop, Gauge, GitCompareArrows, Loader2, MessageSquareWarning, ScanLine } from "lucide-react";
import { generateGradcam, getGroundTruthComparison, getLocalizationPreview, submitFeedback } from "@/lib/api";
import { ProtectedImage } from "@/components/protected-artifact";
import type { Analysis } from "@/lib/types";

export function AnalysisTools({ analysis }: { analysis: Analysis }) {
  const [threshold, setThreshold] = useState(0.55);
  const [sourceId, setSourceId] = useState("");
  const [selectedRegion, setSelectedRegion] = useState<number | null>(null);
  const [reportMessage, setReportMessage] = useState("");

  const localization = useMutation({ mutationFn: () => getLocalizationPreview(analysis.id, threshold) });
  const groundTruth = useMutation({ mutationFn: () => getGroundTruthComparison(analysis.id, sourceId.trim(), threshold) });
  const gradcam = useMutation({ mutationFn: () => generateGradcam(analysis.id) });
  const feedback = useMutation({
    mutationFn: () => submitFeedback(`Analysis review request: ${analysis.filename}`, `Analysis ID: ${analysis.id}\n\n${reportMessage.trim()}`),
    onSuccess: () => setReportMessage(""),
  });

  return (
    <section className="mt-8 space-y-5">
      <div className="card p-5">
        <div className="flex items-center gap-2"><Gauge className="text-cyan-300" size={19} /><h2 className="font-bold">Localization threshold explorer</h2></div>
        <p className="mt-2 text-sm text-slate-400">Recalculate displayed area and regions from the saved neural probability map without re-running the trained model.</p>
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <input aria-label="Localization threshold" className="w-64 accent-cyan-400" type="range" min="0.05" max="0.95" step="0.01" value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} />
          <b className="text-cyan-300">{threshold.toFixed(2)}</b>
          <button className="rounded-lg border border-slate-700 px-3 py-2 text-sm" onClick={() => localization.mutate()} disabled={localization.isPending}>
            {localization.isPending ? "Updating…" : "Preview threshold"}
          </button>
        </div>
        {localization.data && <div className="mt-4 grid gap-3 sm:grid-cols-3"><Stat label="Highlighted area" value={`${localization.data.highlighted_area_pct.toFixed(2)}%`} /><Stat label="Connected regions" value={String(localization.data.regions.length)} /><Stat label="Threshold" value={localization.data.threshold.toFixed(2)} /></div>}
        {localization.isError && <ErrorText error={localization.error} />}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card p-5">
          <div className="flex items-center gap-2"><ScanLine className="text-cyan-300" size={19} /><h2 className="font-bold">Grad-CAM explanation</h2></div>
          <p className="mt-2 text-sm text-slate-400">Generate a separate image-classification explanation from the same saved checkpoint.</p>
          <button className="mt-4 rounded-lg border border-slate-700 px-3 py-2 text-sm" onClick={() => gradcam.mutate()} disabled={gradcam.isPending}>
            {gradcam.isPending ? <span className="inline-flex items-center gap-2"><Loader2 className="animate-spin" size={15} />Generating…</span> : "Generate Grad-CAM"}
          </button>
          {gradcam.data && <div className="mt-4"><ProtectedImage path={gradcam.data.artifact} alt="Grad-CAM explanation" className="max-h-80 w-full rounded-lg object-contain" /><p className="mt-2 text-xs text-slate-500">{gradcam.data.method}</p></div>}
          {gradcam.isError && <ErrorText error={gradcam.error} />}
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2"><GitCompareArrows className="text-cyan-300" size={19} /><h2 className="font-bold">Ground-truth mask comparison</h2></div>
          <p className="mt-2 text-sm text-slate-400">For an AutoSplice dataset image, enter its source ID to compare the predicted map with its labelled mask.</p>
          <div className="mt-4 flex gap-2"><input value={sourceId} onChange={(event) => setSourceId(event.target.value)} placeholder="Example: 39576" className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" /><button className="rounded-lg border border-slate-700 px-3 py-2 text-sm" onClick={() => groundTruth.mutate()} disabled={!sourceId.trim() || groundTruth.isPending}>Compare</button></div>
          {groundTruth.data && <div className="mt-4 grid gap-3 sm:grid-cols-2"><Stat label="Dice" value={groundTruth.data.dice.toFixed(3)} /><Stat label="IoU" value={groundTruth.data.iou.toFixed(3)} /><ProtectedImage path={groundTruth.data.ground_truth_mask} alt="Ground-truth mask" className="max-h-48 w-full rounded-lg object-contain sm:col-span-2" /></div>}
          {groundTruth.isError && <ErrorText error={groundTruth.error} />}
        </div>
      </div>

      <div className="card p-5">
        <div className="flex items-center gap-2"><Crop className="text-cyan-300" size={19} /><h2 className="font-bold">Interactive suspicious regions</h2></div>
        <p className="mt-2 text-sm text-slate-400">Select a detected region to inspect a zoomed crop from the saved original image.</p>
        {analysis.regions.length === 0 ? <p className="mt-3 text-sm text-slate-500">No suspicious region is available for this result.</p> : <div className="mt-4 flex flex-wrap gap-2">{analysis.regions.map((region) => <button key={region.index} onClick={() => setSelectedRegion(region.index)} className={`rounded-lg px-3 py-2 text-sm ${selectedRegion === region.index ? "bg-cyan-400 font-bold text-slate-950" : "border border-slate-700"}`}>Region #{region.index} · {(region.mean_evidence * 100).toFixed(1)}%</button>)}</div>}
        {selectedRegion !== null && <div className="mt-4"><ProtectedImage path={`/api/v1/analyses/${analysis.id}/regions/${selectedRegion}/crop`} alt={`Region ${selectedRegion} crop`} className="max-h-96 w-full rounded-lg object-contain" /></div>}
      </div>

      <div className="card p-5">
        <div className="flex items-center gap-2"><MessageSquareWarning className="text-amber-300" size={19} /><h2 className="font-bold">Human review / report an uncertain result</h2></div>
        <p className="mt-2 text-sm text-slate-400">Submit a review request with this analysis ID. It is stored in the issue queue for a reviewer.</p>
        <textarea value={reportMessage} onChange={(event) => setReportMessage(event.target.value)} rows={3} placeholder="Explain why this result needs review…" className="mt-4 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm" />
        <button className="mt-3 rounded-lg border border-slate-700 px-3 py-2 text-sm" onClick={() => feedback.mutate()} disabled={reportMessage.trim().length < 2 || feedback.isPending}>{feedback.isSuccess ? "Review request submitted" : feedback.isPending ? "Submitting…" : "Submit review request"}</button>
        {feedback.isError && <ErrorText error={feedback.error} />}
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-slate-800 bg-slate-950 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-lg font-bold text-cyan-300">{value}</div></div>; }
function ErrorText({ error }: { error: Error }) { return <p className="mt-3 text-sm text-red-300">{error.message}</p>; }
