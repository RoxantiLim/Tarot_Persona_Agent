import { clearLocalState, loadLocalState, saveLocalState } from "@/lib/local-storage";
import type { CardInput, ReadingResponse } from "@/lib/types";

export const readingStateKey = "tarot-persona:reading-state";
export const readingHistoryKey = "tarot-persona:reading-history";
export const readingStateVersion = 1;
export const readingHistoryVersion = 1;
export const maxReadingHistoryItems = 10;

export const emptySelectedCards: CardInput[] = [
  { name: "", orientation: "正位" },
  { name: "", orientation: "正位" },
  { name: "", orientation: "正位" },
];

export type ReadingSavedState = {
  readerId: string;
  question: string;
  selectedCards: CardInput[];
  result: ReadingResponse | null;
};

export type ReadingHistoryItem = ReadingSavedState & {
  id: string;
  savedAt: string;
  readerName: string;
};

export function loadReadingState() {
  return loadLocalState<ReadingSavedState>(readingStateKey, readingStateVersion);
}

export function saveReadingState(state: ReadingSavedState) {
  saveLocalState<ReadingSavedState>(readingStateKey, readingStateVersion, state);
}

export function clearReadingState() {
  clearLocalState(readingStateKey);
}

export function loadReadingHistory() {
  return loadLocalState<ReadingHistoryItem[]>(readingHistoryKey, readingHistoryVersion) ?? [];
}

export function saveReadingHistory(history: ReadingHistoryItem[]) {
  saveLocalState<ReadingHistoryItem[]>(readingHistoryKey, readingHistoryVersion, history);
}

export function clearReadingHistory() {
  clearLocalState(readingHistoryKey);
}

export function addReadingHistoryItem(state: ReadingSavedState, readerName: string, result: ReadingResponse) {
  const nextItem: ReadingHistoryItem = {
    ...state,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    savedAt: new Date().toISOString(),
    readerName,
    selectedCards: state.selectedCards.map((card) => ({ ...card })),
    result,
  };
  const nextHistory = [nextItem, ...loadReadingHistory()].slice(0, maxReadingHistoryItems);
  saveReadingHistory(nextHistory);
  return nextHistory;
}
