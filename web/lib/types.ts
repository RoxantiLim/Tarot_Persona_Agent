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
  deepseek_configured: boolean;
  index_exists: boolean;
  local_index_exists: boolean;
  chroma_index_exists: boolean;
  retrieval_mode: string;
  vector_store_backend: string;
  embedding_model: string;
  embedding_device: string;
  llm_model: string;
  knowledge_chunks_count: number;
  reviewed_cases_count: number;
  persona_files_count: number;
  cards_count: number;
  readers_count: number;
  status_messages: string[];
};
