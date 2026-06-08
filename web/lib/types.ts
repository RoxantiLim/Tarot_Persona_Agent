export type CardInput = {
  name: string;
  orientation: "正位" | "逆位";
};

export type Reader = {
  reader_id: string;
  display_name: string;
  tone: string;
  reasoning_style: string;
};

export type SourceDocument = {
  content: string;
  source_file: string;
  page: number | string | null;
  quality_status: string;
  quality_reasons: string | string[];
  retrieval_score?: number;
  rerank_score?: number;
  metadata: Record<string, unknown>;
};

export type KnowledgeResponse = {
  answer: string;
  error: string;
  sources: string[];
  documents: SourceDocument[];
};

export type ReadingResponse = {
  answer: string;
  debug: Record<string, unknown>;
  knowledge_docs: SourceDocument[];
  similar_cases: Record<string, unknown>[];
};

export type HealthResponse = {
  ok: boolean;
  index_exists: boolean;
  retrieval_mode: string;
  vector_store_backend: string;
  embedding_model: string;
  llm_model: string;
  cards_count: number;
  readers_count: number;
};
