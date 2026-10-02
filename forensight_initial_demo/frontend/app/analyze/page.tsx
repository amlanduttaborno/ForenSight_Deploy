"use client";

import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ImagePlus, Loader2, ScanSearch } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ResultDashboard } from "@/components/result-dashboard";
import { createAnalysis, sessionToken } from "@/lib/api";
import { usePreferences } from "@/components/preferences";
import type { Analysis } from "@/lib/types";

const schema = z.object({ caption: z.string().max(1000, "Keep the caption below 1000 characters") });
type FormValues = z.infer<typeof schema>;
type BatchOutcome = { results: Analysis[]; failures: Array<{ filename: string; message: string }> };

export default function AnalyzePage() {
  const { t } = usePreferences();
  const [files, setFiles] = useState<File[]>([]);
  const [signedIn, setSignedIn] = useState(false);
  const preview = useMemo(() => (files[0] ? URL.createObjectURL(files[0]) : null), [files]);
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { caption: "" } });
  const mutation = useMutation({
    mutationFn: async ({ selectedFiles, caption }: { selectedFiles: File[]; caption: string }): Promise<BatchOutcome> => {
      const results: Analysis[] = [];
      const failures: Array<{ filename: string; message: string }> = [];
      for (const selectedFile of selectedFiles) {
        try { results.push(await createAnalysis(selectedFile, caption)); }
        catch (error) { failures.push({ filename: selectedFile.name, message: error instanceof Error ? error.message : "Analysis failed" }); }
      }
      return { results, failures };
    },
  });

  useEffect(() => { setSignedIn(Boolean(sessionToken())); }, []);
  const onDrop = useCallback((accepted: File[]) => { setFiles(accepted); mutation.reset(); }, [mutation]);
  const dropzone = useDropzone({ onDrop, accept: { "image/jpeg": [], "image/png": [], "image/webp": [] }, maxFiles: 8 });
  const submit = form.handleSubmit(({ caption }) => { if (files.length && signedIn) mutation.mutate({ selectedFiles: files, caption }); });

  return (
    <div className="mx-auto max-w-7xl p-6 md:p-10">
      <div className="badge border-cyan-500/40 bg-cyan-500/10 text-cyan-200">{t("Image + optional text input", "ইমেজ + ঐচ্ছিক লেখা ইনপুট")}</div>
      <h1 className="mt-5 text-4xl font-black">{t("Analyze Image", "ইমেজ বিশ্লেষণ")}</h1>
      <p className="mt-3 max-w-3xl text-slate-400">{t("Upload JPG, PNG, or WEBP files for trained-model classification and pixel-level localization. Select up to eight images for a sequential batch job; each completed image is saved separately.", "প্রশিক্ষিত মডেলে বিশ্লেষণের জন্য JPG, PNG বা WEBP আপলোড করুন। একসাথে সর্বোচ্চ আটটি ইমেজ ব্যাচ হিসেবে চালানো যায়।")}</p>
      {!signedIn && <div className="mt-5 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100">{t("Sign in is required before verification. Each completed analysis costs 10 tokens and is saved in your private history.", "যাচাইকরণের আগে সাইন ইন প্রয়োজন। প্রতিটি সম্পন্ন বিশ্লেষণে ১০ টোকেন খরচ হয় এবং ব্যক্তিগত ইতিহাসে সংরক্ষিত থাকে।")} <Link href="/account" className="ml-2 font-bold underline">{t("Sign in or register", "সাইন ইন বা নিবন্ধন করুন")}</Link></div>}
      <form onSubmit={submit} className="card mt-8 p-5 md:p-7">
        <div {...dropzone.getRootProps()} className={`cursor-pointer rounded-2xl border-2 border-dashed p-7 text-center transition ${dropzone.isDragActive ? "border-cyan-300 bg-cyan-300/10" : "border-slate-700 bg-slate-950/50"}`}>
          <input {...dropzone.getInputProps()} />
          {preview ? <div className="flex flex-col items-center"><img src={preview} alt={t("Preview", "প্রিভিউ")} className="max-h-72 rounded-xl object-contain" /><div className="mt-3 text-sm text-slate-300">{files.length === 1 ? files[0].name : `${files.length} images selected for one batch job`}</div></div> : <div className="py-8"><ImagePlus className="mx-auto text-cyan-300" size={38} /><div className="mt-4 font-bold">{t("Drop up to 8 images here or click to browse", "এখানে সর্বোচ্চ ৮টি ইমেজ ছাড়ুন বা ব্রাউজ করতে ক্লিক করুন")}</div><div className="mt-2 text-sm text-slate-500">JPG · PNG · WEBP</div></div>}
        </div>
        <label className="mt-6 block text-sm font-bold">{t("Accompanying caption / context", "সংশ্লিষ্ট ক্যাপশন / প্রেক্ষাপট")} <span className="font-normal text-slate-500">{t("(optional; applied to every selected image)", "(ঐচ্ছিক; সব নির্বাচিত ইমেজে প্রযোজ্য)")}</span></label>
        <textarea {...form.register("caption")} rows={4} placeholder={t("Example: A person standing beside a red vehicle…", "উদাহরণ: লাল গাড়ির পাশে দাঁড়িয়ে থাকা একজন ব্যক্তি…")} className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-4 outline-none focus:border-cyan-400" />
        <p className="mt-2 text-xs text-slate-500">{t("When supplied, the caption is evaluated by the trained CLIP-fusion workflow and its consistency score appears in each result.", "ক্যাপশন দেওয়া হলে প্রশিক্ষিত CLIP-ফিউশন ওয়ার্কফ্লোতে প্রতিটি ইমেজের সাথে মূল্যায়ন করা হয়।")}</p>
        <button disabled={!signedIn || !files.length || mutation.isPending} className="mt-6 inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-6 py-3 font-black text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{mutation.isPending ? <><Loader2 className="animate-spin" size={18} />{t("Processing…", "প্রক্রিয়াকরণ হচ্ছে…")}</> : <><ScanSearch size={18} />{files.length > 1 ? `${t("Run batch analysis", "ব্যাচ বিশ্লেষণ চালান")} (${files.length})` : t("Run trained analysis", "প্রশিক্ষিত বিশ্লেষণ চালান")}</>}</button>
        {mutation.isError && <div className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">{mutation.error.message}</div>}
      </form>
      {mutation.data && <div className="mt-6"><div className="card p-4 text-sm text-slate-300">{mutation.data.results.length} image(s) completed and saved separately in History.{mutation.data.failures.length > 0 && <div className="mt-2 text-amber-300">{mutation.data.failures.map((item) => <div key={item.filename}>{item.filename}: {item.message}</div>)}</div>}</div>{mutation.data.results.at(-1) && <ResultDashboard result={mutation.data.results.at(-1)!} />}</div>}
    </div>
  );
}
