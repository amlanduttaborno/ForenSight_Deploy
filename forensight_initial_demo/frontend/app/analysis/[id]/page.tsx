"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AnalysisTools } from "@/components/analysis-tools";
import { ResultDashboard } from "@/components/result-dashboard";
import { apiJson, sessionToken } from "@/lib/api";
import { usePreferences } from "@/components/preferences";
import type { Analysis } from "@/lib/types";

export default function SavedAnalysisPage() {
  const { t } = usePreferences();
  const params = useParams<{ id: string }>();
  const signedIn = Boolean(sessionToken());
  const query = useQuery({
    queryKey: ["analysis", params.id],
    queryFn: () => apiJson<Analysis>(`/analyses/${params.id}`),
    enabled: signedIn && Boolean(params.id),
  });

  if (!signedIn) {
    return <main className="mx-auto max-w-7xl p-6 md:p-10"><p>{t("Sign in is required to reopen this saved result.", "সংরক্ষিত ফলাফল দেখতে সাইন ইন করুন।")} <Link href="/account" className="text-cyan-300 underline">{t("Sign in", "সাইন ইন")}</Link></p></main>;
  }
  if (query.isLoading) return <main className="mx-auto max-w-7xl p-6 md:p-10">{t("Loading saved result…", "সংরক্ষিত ফলাফল লোড হচ্ছে…")}</main>;
  if (query.isError || !query.data) return <main className="mx-auto max-w-7xl p-6 md:p-10">{t("This saved analysis could not be opened.", "এই সংরক্ষিত বিশ্লেষণ খোলা যায়নি।")}</main>;

  return (
    <main className="mx-auto max-w-7xl p-6 md:p-10">
      <Link href="/history" className="text-sm text-cyan-300">← {t("Back to history", "ইতিহাসে ফিরুন")}</Link>
      <ResultDashboard result={query.data} />
      <AnalysisTools analysis={query.data} />
    </main>
  );
}
