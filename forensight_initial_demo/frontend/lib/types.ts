export type Region = {
  index: number;
  x: number;
  y: number;
  width: number;
  height: number;
  area_pct: number;
  mean_evidence: number;
};

export type Analysis = {
  id: string;
  filename: string;
  image_hash: string;
  verdict: string;
  preliminary_score: number;
  manipulated_area_pct: number;
  region_count: number;
  width: number;
  height: number;
  caption: string;
  caption_provided: boolean;
  multimodal_status: string;
  model_status: string;
  model_version: string;
  consistency_score?: number;
  clip_similarity?: number;
  warning: string;
  regions: Region[];
  artifacts: {
    original: string;
    overlay: string;
    mask: string;
    heatmap: string;
    probability_map: string;
    report: string;
  };
  created_at: string;
};

export type ResearchStatus = {
  project: string;
  current_stage: string;
  completed: string[];
  pending: string[];
  demo_message: string;
};

export type LocalizationPreview = {
  threshold: number;
  highlighted_area_pct: number;
  regions: Array<{ x: number; y: number; width: number; height: number; area_pct: number }>;
};

export type GroundTruthComparison = {
  source_id: string;
  threshold: number;
  dice: number;
  iou: number;
  ground_truth_mask: string;
};

export type InvestigationCase = {
  id: string;
  title: string;
  description: string;
  status: "open" | "closed" | "archived";
  created_at: string;
  analyses: Array<{ id: string; filename: string; verdict: string; score: number; created_at: string }>;
};

export type EvaluationData = {
  source: string;
  metrics: Record<string, Record<string, number>>;
  run_config: Record<string, unknown>;
  compression: Array<Record<string, string>>;
  ablation: Array<Record<string, string>>;
  training: Array<Record<string, string>>;
};
