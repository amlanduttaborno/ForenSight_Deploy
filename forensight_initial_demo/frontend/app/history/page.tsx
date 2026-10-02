"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3, CopyCheck, FolderPlus, GitCompareArrows, Search } from "lucide-react";
import { addAnalysisToCase, compareAnalyses, createCase, getAnalyses, getCases, getDuplicates, sessionToken } from "@/lib/api";
import { ProtectedImage } from "@/components/protected-artifact";
import { usePreferences } from "@/components/preferences";

export default function HistoryPage() {
  const { language, t } = usePreferences();
  const signedIn = Boolean(sessionToken());
  const [search, setSearch] = useState("");
  const [verdictFilter, setVerdictFilter] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [duplicateMessage, setDuplicateMessage] = useState("");
  const [caseTitle, setCaseTitle] = useState("");
  const [caseDescription, setCaseDescription] = useState("");
  const [caseId, setCaseId] = useState("");
  const client = useQueryClient();
  const filters = useMemo(() => ({ query: search, verdict: verdictFilter }), [search, verdictFilter]);
  const query = useQuery({ queryKey: ["analyses", filters], queryFn: () => getAnalyses(filters), enabled: signedIn });
  const cases = useQuery({ queryKey: ["cases"], queryFn: getCases, enabled: signedIn });
  const compare = useMutation({ mutationFn: () => compareAnalyses(selected[0], selected[1]) });
  const addToCase = useMutation({ mutationFn: () => addAnalysisToCase(caseId, selected[0]), onSuccess: () => client.invalidateQueries({ queryKey: ["cases"] }) });
  const newCase = useMutation({ mutationFn: () => createCase(caseTitle, caseDescription), onSuccess: (item) => { setCaseId(item.id); setCaseTitle(""); setCaseDescription(""); client.invalidateQueries({ queryKey: ["cases"] }); } });
  const verdict = (value: string) => value === "LIKELY MANIPULATED" ? t("LIKELY MANIPULATED", "সম্ভবত বিকৃত") : value === "LIKELY AUTHENTIC" ? t("LIKELY AUTHENTIC", "সম্ভবত আসল") : value;

  function toggle(id: string) {
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length < 2 ? [...current, id] : [current[1], id]);
  }
  async function duplicates(hash: string) {
    try {
      const rows = await getDuplicates(hash);
      setDuplicateMessage(rows.length > 1 ? `${rows.length} saved analyses have this identical SHA-256 file hash.` : "No other saved analysis has this SHA-256 file hash.");
    } catch (error) { setDuplicateMessage(error instanceof Error ? error.message : "Could not check duplicates."); }
  }

  if (!signedIn) return <div className="mx-auto max-w-7xl p-6 md:p-10"><h1 className="text-4xl font-black">{t("Analysis History", "বিশ্লেষণের ইতিহাস")}</h1><p className="mt-4 text-slate-400">{t("Sign in to view your private saved analyses.", "আপনার ব্যক্তিগত সংরক্ষিত বিশ্লেষণ দেখতে সাইন ইন করুন। ")}<Link className="text-cyan-300 underline" href="/account">{t("Sign in", "সাইন ইন")}</Link></p></div>;

  return (
    <div className="mx-auto max-w-7xl p-6 md:p-10">
      <h1 className="text-4xl font-black">{t("Analysis History", "বিশ্লেষণের ইতিহাস")}</h1>
      <p className="mt-3 text-slate-400">{t("Search, compare, investigate, and reopen your saved trained-model records.", "সংরক্ষিত ফলাফল অনুসন্ধান, তুলনা ও পুনরায় খুলুন।")}</p>

      <section className="card mt-6 grid gap-3 p-4 md:grid-cols-[1fr_220px_auto]">
        <label className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3"><Search size={16} className="text-slate-500" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search filename or SHA-256", "ফাইলনাম বা SHA-256 খুঁজুন")} className="w-full bg-transparent py-2 text-sm outline-none" /></label>
        <select value={verdictFilter} onChange={(event) => setVerdictFilter(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"><option value="">{t("All verdicts", "সব রায়")}</option><option value="LIKELY AUTHENTIC">{t("Likely authentic", "সম্ভবত আসল")}</option><option value="LIKELY MANIPULATED">{t("Likely manipulated", "সম্ভবত বিকৃত")}</option></select>
        <button onClick={() => compare.mutate()} disabled={selected.length !== 2 || compare.isPending} className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950 disabled:opacity-40"><GitCompareArrows size={16} />{t("Compare selected", "নির্বাচিত তুলনা করুন")}</button>
      </section>
      {compare.data && <section className="card mt-4 grid gap-4 p-4 md:grid-cols-2">{compare.data.map((item) => <Link key={item.id} href={`/analysis/${item.id}`} className="rounded-xl border border-slate-800 p-4 hover:border-cyan-500/60"><div className="font-bold">{item.filename}</div><div className="mt-2 text-cyan-300">{verdict(item.verdict)} · {(item.preliminary_score * 100).toFixed(1)}%</div><div className="mt-2 text-sm text-slate-400">{item.region_count} regions · {item.manipulated_area_pct.toFixed(2)}% highlighted</div></Link>)}</section>}
      {compare.isError && <p className="mt-3 text-sm text-red-300">{compare.error.message}</p>}

      <section className="card mt-6 p-5">
        <div className="flex items-center gap-2"><FolderPlus className="text-cyan-300" size={19} /><h2 className="font-bold">Case-based investigation</h2></div>
        <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]"><input value={caseTitle} onChange={(event) => setCaseTitle(event.target.value)} placeholder="Case title" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" /><input value={caseDescription} onChange={(event) => setCaseDescription(event.target.value)} placeholder="Description (optional)" className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" /><button onClick={() => newCase.mutate()} disabled={caseTitle.trim().length < 2 || newCase.isPending} className="rounded-lg border border-slate-700 px-3 py-2 text-sm">Create case</button></div>
        <div className="mt-3 flex flex-wrap items-center gap-3"><select value={caseId} onChange={(event) => setCaseId(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"><option value="">Select a case</option>{cases.data?.map((item) => <option key={item.id} value={item.id}>{item.title} ({item.analyses.length})</option>)}</select><button onClick={() => addToCase.mutate()} disabled={!caseId || selected.length !== 1 || addToCase.isPending} className="rounded-lg border border-slate-700 px-3 py-2 text-sm disabled:opacity-40">Add one selected analysis to case</button>{addToCase.isSuccess && <span className="text-sm text-emerald-300">Saved to case.</span>}</div>
      </section>

      {duplicateMessage && <p className="mt-4 rounded-lg border border-slate-700 p-3 text-sm text-slate-300">{duplicateMessage}</p>}
      <div className="mt-6 space-y-3">
        {query.isLoading && <div className="card p-5">{t("Loading…", "লোড হচ্ছে…")}</div>}
        {query.data?.length === 0 && <div className="card p-5 text-slate-400">{t("No matching analysis was found.", "কোনো মিলিত বিশ্লেষণ পাওয়া যায়নি।")}</div>}
        {query.data?.map((item) => <article key={item.id} className="card grid gap-4 p-4 md:grid-cols-[auto_110px_1fr_auto] md:items-center"><input aria-label={`Select ${item.filename}`} checked={selected.includes(item.id)} onChange={() => toggle(item.id)} type="checkbox" className="h-4 w-4 accent-cyan-400" /><ProtectedImage path={item.artifacts.overlay} alt="Overlay" className="h-24 w-28 rounded-lg object-cover" /><div><div className="font-bold">{item.filename}</div><div className="mt-1 text-sm text-slate-400">{verdict(item.verdict)}</div><div className="mt-2 flex items-center gap-2 text-xs text-slate-500"><Clock3 size={14} />{new Date(item.created_at).toLocaleString(language === "bn" ? "bn-BD" : "en-US")}</div></div><div className="text-left md:text-right"><div className="text-2xl font-black">{(item.preliminary_score * 100).toFixed(1)}%</div><button onClick={() => void duplicates(item.image_hash)} className="mt-2 inline-flex items-center gap-1 text-xs text-cyan-300"><CopyCheck size={14} />Check duplicates</button><Link href={`/analysis/${item.id}`} className="mt-2 block text-sm font-semibold text-cyan-300">{t("Reopen result", "ফলাফল খুলুন")} →</Link></div></article>)}
      </div>
    </div>
  );
}
