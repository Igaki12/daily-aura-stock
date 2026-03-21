export type PipelineState =
  | "idle"
  | "ready"
  | "summarizing"
  | "embedding"
  | "ranking"
  | "predicted"
  | "error";

export type ApiKeyState = {
  value: string;
  savedAt?: string;
};

export type SimilarityResult = {
  marketEffectiveDateJst: string;
  score: number;
  distance: number;
};

export type MarketRecord = {
  n225Close: number | null;
  n225PrevCloseChangePct: number | null;
  topixProxyClose: number | null;
  topixProxyPrevCloseChangePct: number | null;
};

export type DailyRecord = {
  marketEffectiveDateJst: string;
  articleCount: number;
  sampleHeadlines: string[];
  summary: string;
  embedding: number[];
  embeddingVectorLength: number;
  topics: {
    brands: Array<{ name: string; count: number; ratio: number }>;
    genres: Array<{ name: string; count: number; ratio: number }>;
    countries: Array<{ name: string; count: number; ratio: number }>;
    companies: Array<{ name: string; count: number; ratio: number }>;
  };
  market: MarketRecord;
};

export type DemoData = {
  generatedAt: string;
  sourceRange: string;
  records: DailyRecord[];
};

export type ActivityLog = {
  timestamp: string;
  level: "info" | "warn" | "error";
  message: string;
};
