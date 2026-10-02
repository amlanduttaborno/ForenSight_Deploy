"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, FlaskConical, History, ScanSearch, User } from "lucide-react";
import { usePreferences } from "@/components/preferences";

export function Nav() {
  const pathname = usePathname();
  const { language, setLanguage, t } = usePreferences();
  const links = [
    { href: "/", en: "Dashboard", bn: "ড্যাশবোর্ড", icon: Activity },
    { href: "/analyze", en: "Analyze", bn: "বিশ্লেষণ", icon: ScanSearch },
    { href: "/history", en: "History", bn: "ইতিহাস", icon: History },
    { href: "/research", en: "Research", bn: "গবেষণা", icon: FlaskConical },
    { href: "/account", en: "Sign in", bn: "সাইন ইন", icon: User },
  ];
  return <aside className="border-b border-slate-800 bg-slate-950/90 md:min-h-screen md:w-64 md:border-b-0 md:border-r"><div className="p-6"><div className="text-xl font-black tracking-tight">ForenSight</div><div className="mt-1 text-xs text-cyan-300">{t("AI Image Forensics Prototype", "এআই ইমেজ ফরেনসিকস প্রোটোটাইপ")}</div></div><nav className="flex gap-2 overflow-x-auto px-3 pb-4 md:flex-col">{links.map(({ href, en, bn, icon: Icon }) => <Link key={href} href={href} className={`flex min-w-fit items-center gap-3 rounded-xl px-4 py-3 text-sm transition ${pathname === href ? "bg-cyan-400 text-slate-950" : "text-slate-300 hover:bg-slate-900"}`}><Icon size={18} /> {t(en, bn)}</Link>)}</nav><div className="m-4"><button onClick={() => setLanguage(language === "en" ? "bn" : "en")} className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-bold">{language === "en" ? "বাংলা" : "EN"}</button></div><div className="m-4 rounded-xl border border-cyan-500/40 bg-cyan-500/10 p-4 text-xs text-cyan-50"><strong>{t("TRAINED MODEL", "প্রশিক্ষিত মডেল")}</strong><p className="mt-2 leading-relaxed">{t("best.pt multimodal checkpoint is active for analysis.", "বিশ্লেষণের জন্য best.pt মাল্টিমোডাল চেকপয়েন্ট সক্রিয়।")}</p></div></aside>;
}
