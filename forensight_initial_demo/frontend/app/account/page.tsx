"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL, apiJson, authHeaders, sessionToken } from "@/lib/api";
import { usePreferences } from "@/components/preferences";

type User = { name: string; email: string; token_balance: number };

export default function AccountPage() {
  const router = useRouter();
  const { t } = usePreferences();
  const [user, setUser] = useState<User | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [referralCode, setReferralCode] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    if (!sessionToken()) return;
    try {
      setUser(await apiJson<User>("/account/me"));
    } catch {
      localStorage.removeItem("forensight_token");
      setUser(null);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function submit(register: boolean) {
    if (!email.trim()) {
      setMessage(t("Enter your email address.", "আপনার ইমেইল ঠিকানা লিখুন।"));
      return;
    }
    if (password.length < 8) {
      setMessage(t("Password must contain at least 8 characters.", "পাসওয়ার্ডে কমপক্ষে ৮টি অক্ষর থাকতে হবে।"));
      return;
    }
    if (register && name.trim().length < 2) {
      setMessage(t("Enter a name with at least 2 characters.", "কমপক্ষে ২ অক্ষরের নাম লিখুন।"));
      return;
    }

    const response = await fetch(`${API_URL}/api/v1/auth/${register ? "register" : "login"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(register ? { name, email, password, referral_code: referralCode } : { email, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map((item: { msg?: string }) => item.msg).join(". ") : data.detail;
      setMessage(detail || t("Request failed.", "অনুরোধটি সম্পন্ন হয়নি।"));
      return;
    }
    localStorage.setItem("forensight_token", data.access_token);
    await refresh();
    router.replace("/");
  }

  async function signOut() {
    await fetch(`${API_URL}/api/v1/auth/logout`, { method: "POST", headers: authHeaders() });
    localStorage.removeItem("forensight_token");
    setUser(null);
  }

  if (user) {
    return (
      <main className="mx-auto max-w-2xl p-6 md:p-10">
        <h1 className="text-4xl font-black">{t("Account", "অ্যাকাউন্ট")}</h1>
        <section className="card mt-6 p-6">
          <h2 className="text-xl font-bold">{t("Signed in", "সাইন ইন করা আছে")}</h2>
          <p className="mt-3">{user.name}</p>
          <p className="text-sm text-slate-400">{user.email}</p>
          <p className="mt-5 text-lg">
            {t("Token balance", "টোকেন ব্যালেন্স")}: <b className="text-cyan-300">{user.token_balance}</b>
          </p>
          <p className="mt-2 text-sm text-slate-400">
            {t(
              "Each verification costs 10 tokens and is saved in your history.",
              "প্রতিটি যাচাইকরণে ১০ টোকেন খরচ হয় এবং এটি আপনার ইতিহাসে সংরক্ষিত থাকে।",
            )}
          </p>
          <div className="mt-5 flex gap-3">
            <button onClick={() => router.push("/analyze")} className="rounded bg-cyan-400 px-4 py-2 font-bold text-slate-950">
              {t("Analyze image", "ইমেজ বিশ্লেষণ করুন")}
            </button>
            <button onClick={signOut} className="rounded border px-4 py-2">
              {t("Sign out", "সাইন আউট")}
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-md p-6 md:p-10">
      <h1 className="text-4xl font-black">{t("Sign in to ForenSight", "ForenSight-এ সাইন ইন করুন")}</h1>
      <p className="mt-3 text-slate-400">
        {t("Register once to receive 1,000 tokens and keep your own analysis history.", "১,০০০ টোকেন পেতে এবং আপনার বিশ্লেষণের ইতিহাস রাখতে একবার নিবন্ধন করুন।")}
      </p>
      <section className="card mt-6 space-y-3 p-5">
        <input className="w-full rounded bg-slate-950 p-3" placeholder={t("Name (for registration)", "নাম (নিবন্ধনের জন্য)")} value={name} onChange={(event) => setName(event.target.value)} />
        <input className="w-full rounded bg-slate-950 p-3" type="email" placeholder={t("Email", "ইমেইল")} value={email} onChange={(event) => setEmail(event.target.value)} />
        <input className="w-full rounded bg-slate-950 p-3" type="password" placeholder={t("Password (at least 8 characters)", "পাসওয়ার্ড (কমপক্ষে ৮ অক্ষর)")} value={password} onChange={(event) => setPassword(event.target.value)} />
        <input className="w-full rounded bg-slate-950 p-3" placeholder={t("Referral code (optional)", "রেফারেল কোড (ঐচ্ছিক)")} value={referralCode} onChange={(event) => setReferralCode(event.target.value)} />
        <div className="flex gap-3">
          <button onClick={() => void submit(false)} className="rounded bg-cyan-400 px-4 py-2 font-bold text-slate-950">{t("Sign in", "সাইন ইন")}</button>
          <button onClick={() => void submit(true)} className="rounded border px-4 py-2">{t("Register", "নিবন্ধন")}</button>
        </div>
        {message && <p className="text-sm text-amber-300">{message}</p>}
      </section>
    </main>
  );
}
