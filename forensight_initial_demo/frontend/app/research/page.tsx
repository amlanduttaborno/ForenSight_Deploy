"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, FlaskConical } from "lucide-react";
import { getEvaluation, getResearchStatus } from "@/lib/api";
import { usePreferences } from "@/components/preferences";

export default function ResearchPage() {
  const { t } = usePreferences();
  const status = useQuery({ queryKey: ["research-status"], queryFn: getResearchStatus });
  const evaluation = useQuery({ queryKey: ["evaluation"], queryFn: getEvaluation });
  const data = status.data;
  return (
    <div className="mx-auto max-w-7xl p-6 md:p-10">
      <div className="flex items-center gap-3"><FlaskConical className="text-cyan-300" /><h1 className="text-4xl font-black">{t("Research & evaluation", "গবেষণা ও মূল্যায়ন")}</h1></div>
      <p className="mt-3 max-w-4xl text-slate-400">{t("Read-only metrics exported by ForenSight_Final.ipynb. They describe the held-out AutoSplice evaluation, not a guarantee for arbitrary external images.", "ForenSight_Final.ipynb থেকে রপ্তানি করা মূল্যায়ন ফলাফল।")}</p>
      {!data ? <div className="card mt-8 p-5">{t("Loading research status…", "গবেষণার অবস্থা লোড হচ্ছে…")}</div> : <>
        <div className="card mt-8 p-6"><div className="text-sm text-cyan-300">{t("Current stage", "বর্তমান ধাপ")}</div><div className="mt-2 text-2xl font-black">{data.current_stage}</div><p className="mt-4 text-sm leading-6 text-slate-300">{data.demo_message}</p></div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2"><section className="card p-6"><h2 className="font-bold">{t("Completed", "সম্পন্ন")}</h2><div className="mt-4 space-y-3">{data.completed.map((item) => <div key={item} className="flex gap-3 text-sm text-slate-300"><CheckCircle2 size={18} className="shrink-0 text-emerald-300" />{item}</div>)}</div></section><section className="card p-6"><h2 className="font-bold">{t("Next steps", "পরবর্তী ধাপ")}</h2><div className="mt-4 space-y-3">{data.pending.map((item) => <div key={item} className="flex gap-3 text-sm text-slate-300"><CircleDashed size={18} className="shrink-0 text-amber-300" />{item}</div>)}</div></section></div>
      </>}
      {evaluation.isLoading && <div className="card mt-5 p-5">Loading evaluation artifacts…</div>}
      {evaluation.data && <EvaluationDashboard data={evaluation.data} />}
      {evaluation.isError && <div className="card mt-5 p-5 text-red-300">{evaluation.error.message}</div>}
    </div>
  );
}

function EvaluationDashboard({ data }: { data: Awaited<ReturnType<typeof getEvaluation>> }) {
  const source = data.metrics.classification_source_balanced ?? {};
  const localization = data.metrics.localization ?? {};
  const matrix = [
    ["True negative", source.tn], ["False positive", source.fp], ["False negative", source.fn], ["True positive", source.tp],
  ];
  return <section className="mt-5 space-y-5"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric title="Source-balanced accuracy" value={percent(source.accuracy)} /><Metric title="ROC-AUC" value={number(source.roc_auc)} /><Metric title="Localization Dice" value={number(localization.dice)} /><Metric title="Localization IoU" value={number(localization.iou)} /></div><div className="grid gap-5 lg:grid-cols-2"><section className="card p-5"><h2 className="font-bold">Held-out confusion matrix</h2><p className="mt-2 text-sm text-slate-400">Classification counts exported by the notebook.</p><div className="mt-4 grid grid-cols-2 gap-3">{matrix.map(([label, value]) => <Metric key={String(label)} title={String(label)} value={String(value ?? "—")} />)}</div></section><section className="card p-5"><h2 className="font-bold">JPEG compression robustness</h2><DataTable rows={data.compression} columns={["jpeg_quality", "roc_auc", "f1", "accuracy", "dice", "iou"]} /></section></div><div className="grid gap-5 lg:grid-cols-2"><section className="card p-5"><h2 className="font-bold">Text-modality ablation</h2><DataTable rows={data.ablation} columns={data.ablation[0] ? Object.keys(data.ablation[0]) : []} /></section><section className="card p-5"><h2 className="font-bold">Thresholds and model configuration</h2><div className="mt-3 space-y-2 text-sm text-slate-300"><div>Classification threshold: <b>{number(source.threshold)}</b></div><div>Mask threshold: <b>{number(localization.mask_threshold)}</b></div><div>Image size: <b>{String(data.run_config.image_size ?? "—")}</b></div><div>RGB backbone: <b>{String(data.run_config.rgb_backbone ?? "—")}</b></div></div></section></div></section>;
}
function Metric({ title, value }: { title: string; value: string }) { return <div className="rounded-xl border border-slate-800 bg-slate-950 p-4"><div className="text-xs text-slate-500">{title}</div><div className="mt-2 text-2xl font-black text-cyan-300">{value}</div></div>; }
function DataTable({ rows, columns }: { rows: Array<Record<string, string>>; columns: string[] }) { return <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-slate-500"><tr>{columns.map((column) => <th key={column} className="p-2">{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index} className="border-t border-slate-800">{columns.map((column) => <td key={column} className="p-2 text-slate-300">{row[column] ?? "—"}</td>)}</tr>)}</tbody></table></div>; }
function number(value: unknown) { return typeof value === "number" ? value.toFixed(3) : "—"; }
function percent(value: unknown) { return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "—"; }
