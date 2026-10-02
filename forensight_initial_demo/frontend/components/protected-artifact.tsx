"use client";

import { useEffect, useState } from "react";
import { absoluteArtifact, authHeaders } from "@/lib/api";

export function ProtectedImage({ path, alt, className }: { path: string; alt: string; className?: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => { let alive = true; let objectUrl = ""; fetch(absoluteArtifact(path), { headers: authHeaders() }).then(async response => { if (!response.ok) throw new Error(); objectUrl = URL.createObjectURL(await response.blob()); if (alive) setUrl(objectUrl); }).catch(() => { if (alive) setUrl(""); }); return () => { alive = false; if (objectUrl) URL.revokeObjectURL(objectUrl); }; }, [path]);
  return url ? <img src={url} alt={alt} className={className} /> : <div className={`${className ?? ""} grid place-items-center bg-slate-950 text-xs text-slate-500`}>Loading…</div>;
}

export async function openProtectedFile(path: string) {
  const response = await fetch(absoluteArtifact(path), { headers: authHeaders() });
  if (!response.ok) throw new Error("Could not open protected file");
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
