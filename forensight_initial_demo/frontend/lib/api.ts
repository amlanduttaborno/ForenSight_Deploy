import type { Analysis, EvaluationData, GroundTruthComparison, InvestigationCase, LocalizationPreview, ResearchStatus } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function sessionToken() {
  return typeof window === "undefined" ? "" : localStorage.getItem("forensight_token") ?? "";
}

export function authHeaders(json = false): HeadersInit {
  const token = sessionToken();
  return { ...(json ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

function responseMessage(detail: unknown, fallback: string) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => item && typeof item === "object" && "msg" in item && typeof item.msg === "string" ? item.msg : fallback).join(". ");
  return fallback;
}

async function ensureOk(response: Response) {
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      message = responseMessage(body.detail, message);
    } catch {}
    throw new Error(message);
  }
  return response;
}

export function absoluteArtifact(path: string) {
  return `${API_URL}${path}`;
}

export async function createAnalysis(file: File, caption: string): Promise<Analysis> {
  const form = new FormData();
  form.append("image", file);
  form.append("caption", caption);
  form.append("analysis_mode", "supervisor-demo");
  const response = await fetch(`${API_URL}/api/v1/analyses`, { method: "POST", body: form, headers: authHeaders() });
  await ensureOk(response);
  return response.json();
}

export async function getAnalyses(filters: { query?: string; verdict?: string } = {}): Promise<Analysis[]> {
  const params = new URLSearchParams();
  if (filters.query?.trim()) params.set("query", filters.query.trim());
  if (filters.verdict?.trim()) params.set("verdict", filters.verdict.trim());
  const suffix = params.size ? `?${params}` : "";
  const response = await fetch(`${API_URL}/api/v1/analyses${suffix}`, { cache: "no-store", headers: authHeaders() });
  await ensureOk(response);
  return response.json();
}

export async function getResearchStatus(): Promise<ResearchStatus> {
  const response = await fetch(`${API_URL}/api/v1/research/status`, { cache: "no-store" });
  await ensureOk(response);
  return response.json();
}

export async function getEvaluation(): Promise<EvaluationData> {
  const response = await fetch(`${API_URL}/api/v1/research/evaluation`, { cache: "no-store" });
  await ensureOk(response);
  return response.json();
}

export async function getLocalizationPreview(id: string, threshold: number): Promise<LocalizationPreview> {
  return apiJson<LocalizationPreview>(`/analyses/${id}/localization-preview?threshold=${encodeURIComponent(threshold)}`);
}

export async function getGroundTruthComparison(id: string, sourceId: string, threshold: number): Promise<GroundTruthComparison> {
  return apiJson<GroundTruthComparison>(`/analyses/${id}/ground-truth-comparison?source_id=${encodeURIComponent(sourceId)}&threshold=${encodeURIComponent(threshold)}`);
}

export async function generateGradcam(id: string): Promise<{ artifact: string; method: string }> {
  return apiJson(`/analyses/${id}/gradcam`, { method: "POST" });
}

export async function getDuplicates(hash: string): Promise<Analysis[]> {
  return apiJson<Analysis[]>(`/analyses/duplicates/${hash}`);
}

export async function compareAnalyses(leftId: string, rightId: string): Promise<Analysis[]> {
  return apiJson<Analysis[]>(`/analyses/compare/${leftId}/${rightId}`);
}

export async function getCases(): Promise<InvestigationCase[]> {
  return apiJson<InvestigationCase[]>("/cases");
}

export async function createCase(title: string, description: string): Promise<InvestigationCase> {
  return apiJson<InvestigationCase>("/cases", { method: "POST", body: JSON.stringify({ title, description }) });
}

export async function addAnalysisToCase(caseId: string, analysisId: string): Promise<InvestigationCase> {
  return apiJson<InvestigationCase>(`/cases/${caseId}/analyses/${analysisId}`, { method: "POST" });
}

export async function submitFeedback(subject: string, message: string): Promise<{ id: string; status: string }> {
  return apiJson("/feedback", { method: "POST", body: JSON.stringify({ subject, message }) });
}

export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, { cache: "no-store", ...options, headers: { ...authHeaders(Boolean(options.body)), ...(options.headers ?? {}) } });
  await ensureOk(response);
  return response.json();
}
