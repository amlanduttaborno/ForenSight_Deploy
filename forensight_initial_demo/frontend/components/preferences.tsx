"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

type Language = "en" | "bn";
type Preferences = { language: Language; setLanguage: (language: Language) => void; t: (en: string, bn: string) => string };
const PreferencesContext = createContext<Preferences | null>(null);

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [language, setRawLanguage] = useState<Language>("en");
  useEffect(() => {
    const saved = localStorage.getItem("forensight_language");
    if (saved === "bn" || saved === "en") setRawLanguage(saved);
  }, []);
  useEffect(() => {
    document.documentElement.lang = language;
    localStorage.setItem("forensight_language", language);
  }, [language]);
  const value = useMemo(() => ({ language, setLanguage: setRawLanguage, t: (en: string, bn: string) => language === "bn" ? bn : en }), [language]);
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error("PreferencesProvider is missing");
  return context;
}
