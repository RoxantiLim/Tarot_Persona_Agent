import { clearLocalState, loadLocalState, saveLocalState } from "@/lib/local-storage";
import type { KnowledgeResponse } from "@/lib/types";

export const modes = ["牌意查询", "主题学习", "资料检索"] as const;
export const modeLabels: Record<KnowledgeMode, string> = {
  牌意查询: "查牌意",
  主题学习: "学主题",
  资料检索: "搜资料",
};
export const orientations = ["不限定", "正位", "逆位"];
export const topics = ["通用", "感情", "事业", "学习", "人际", "灵性成长"];
export const knowledgeStateKey = "tarot-persona:knowledge-state";
export const knowledgeHistoryKey = "tarot-persona:knowledge-history";
export const knowledgeStateVersion = 1;
export const knowledgeHistoryVersion = 1;
export const maxKnowledgeHistoryItems = 10;
export const referenceLevels = [
  { label: "少量", description: "看核心资料", value: 3 },
  { label: "适中", description: "兼顾来源和篇幅", value: 5 },
  { label: "充分", description: "多看几处资料", value: 8 },
];

export type KnowledgeMode = (typeof modes)[number];

export type KnowledgeSavedState = {
  mode: KnowledgeMode;
  cardName: string;
  orientation: string;
  topic: string;
  query: string;
  topK: number;
  result: KnowledgeResponse | null;
};

export type KnowledgeHistoryItem = KnowledgeSavedState & {
  id: string;
  savedAt: string;
};

export function normalizeReferenceLevel(value: number) {
  if (value <= 3) {
    return 3;
  }
  if (value <= 5) {
    return 5;
  }
  return 8;
}

export function buildKnowledgeQuery(state: KnowledgeSavedState) {
  if (state.mode !== "牌意查询") {
    return state.query;
  }

  return [state.cardName, state.orientation, state.topic, state.query].filter(Boolean).join(" ");
}

export function loadKnowledgeState() {
  return loadLocalState<KnowledgeSavedState>(knowledgeStateKey, knowledgeStateVersion);
}

export function saveKnowledgeState(state: KnowledgeSavedState) {
  saveLocalState<KnowledgeSavedState>(knowledgeStateKey, knowledgeStateVersion, state);
}

export function clearKnowledgeState() {
  clearLocalState(knowledgeStateKey);
}

export function loadKnowledgeHistory() {
  return loadLocalState<KnowledgeHistoryItem[]>(knowledgeHistoryKey, knowledgeHistoryVersion) ?? [];
}

export function saveKnowledgeHistory(history: KnowledgeHistoryItem[]) {
  saveLocalState<KnowledgeHistoryItem[]>(knowledgeHistoryKey, knowledgeHistoryVersion, history);
}

export function clearKnowledgeHistory() {
  clearLocalState(knowledgeHistoryKey);
}

export function addKnowledgeHistoryItem(state: KnowledgeSavedState, result: KnowledgeResponse) {
  const nextItem: KnowledgeHistoryItem = {
    ...state,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    savedAt: new Date().toISOString(),
    result,
  };
  const nextHistory = [nextItem, ...loadKnowledgeHistory()].slice(0, maxKnowledgeHistoryItems);
  saveKnowledgeHistory(nextHistory);
  return nextHistory;
}
