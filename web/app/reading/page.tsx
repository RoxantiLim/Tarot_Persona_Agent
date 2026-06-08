"use client";

import { FormEvent, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { CardSelector } from "@/components/card-selector";
import { HistoryList } from "@/components/history-list";
import { LoadingButton } from "@/components/loading-button";
import { ReaderPicker } from "@/components/reader-picker";
import { ResultPanel } from "@/components/result-panel";
import { apiGet } from "@/lib/api";
import { getReaderPresentation } from "@/lib/reader-presentations";
import {
  clearReadingHistory,
  clearReadingState,
  emptySelectedCards,
  loadReadingHistory,
  loadReadingState,
  saveReadingState,
  type ReadingHistoryItem,
  type ReadingSavedState,
} from "@/lib/reading-storage";
import {
  getReadingTaskServerSnapshot,
  getReadingTaskSnapshot,
  startReadingTask,
  subscribeReadingTask,
} from "@/lib/reading-task-store";
import type { CardInput, Reader } from "@/lib/types";

export default function ReadingPage() {
  const [cards, setCards] = useState<string[]>([]);
  const [readers, setReaders] = useState<Reader[]>([]);
  const [readerId, setReaderId] = useState("tarotist_1");
  const [question, setQuestion] = useState("");
  const [selectedCards, setSelectedCards] = useState<CardInput[]>(emptySelectedCards);
  const [result, setResult] = useState<ReadingSavedState["result"]>(null);
  const [error, setError] = useState("");
  const [hasRestoredState, setHasRestoredState] = useState(false);
  const [history, setHistory] = useState<ReadingHistoryItem[]>([]);
  const taskSnapshot = useSyncExternalStore(subscribeReadingTask, getReadingTaskSnapshot, getReadingTaskServerSnapshot);
  const isGenerating = taskSnapshot.status === "running";

  useEffect(() => {
    Promise.all([apiGet<{ cards: string[]; sample_draw: CardInput[] }>("/api/cards"), apiGet<{ readers: Reader[] }>("/api/readers")])
      .then(([cardPayload, readerPayload]) => {
        setCards(cardPayload.cards);
        setReaders(readerPayload.readers);
        setSelectedCards((currentCards) => (currentCards.some((card) => card.name) ? currentCards : cardPayload.sample_draw));
        setReaderId((currentReaderId) => currentReaderId || readerPayload.readers[0]?.reader_id || "tarotist_1");
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    const savedState = loadReadingState();
    if (savedState) {
      setReaderId(savedState.readerId);
      setQuestion(savedState.question);
      setSelectedCards(savedState.selectedCards.length === 3 ? savedState.selectedCards : emptySelectedCards);
      setResult(savedState.result);
    }
    setHistory(loadReadingHistory());
    setHasRestoredState(true);
  }, []);

  useEffect(() => {
    if (!hasRestoredState) {
      return;
    }

    saveReadingState({
      readerId,
      question,
      selectedCards,
      result,
    });
  }, [hasRestoredState, question, readerId, result, selectedCards]);

  const selectedReader = useMemo(() => readers.find((reader) => reader.reader_id === readerId), [readerId, readers]);

  useEffect(() => {
    if (taskSnapshot.status === "idle") {
      return;
    }

    setReaderId(taskSnapshot.state.readerId);
    setQuestion(taskSnapshot.state.question);
    setSelectedCards(taskSnapshot.state.selectedCards);

    if (taskSnapshot.status === "running") {
      setResult(null);
      setError("");
      return;
    }

    if (taskSnapshot.status === "success") {
      setResult(taskSnapshot.result);
      setHistory(loadReadingHistory());
      setError("");
      return;
    }

    setResult(null);
    setError(taskSnapshot.message);
  }, [taskSnapshot]);

  function clearSavedState() {
    if (isGenerating) {
      setError("这次解读还在进行中，完成后再清空当前记录。");
      return;
    }

    clearReadingState();
    setReaderId(readers[0]?.reader_id ?? "tarotist_1");
    setQuestion("");
    setSelectedCards(cards.length ? cards.slice(0, 3).map((name) => ({ name, orientation: "正位" })) : emptySelectedCards);
    setResult(null);
    setError("");
  }

  function restoreHistoryItem(id: string) {
    if (isGenerating) {
      setError("这次解读还在进行中，完成后再打开历史记录。");
      return;
    }

    const item = history.find((historyItem) => historyItem.id === id);
    if (!item) {
      return;
    }

    setReaderId(item.readerId);
    setQuestion(item.question);
    setSelectedCards(item.selectedCards);
    setResult(item.result);
    setError("");
  }

  function clearHistory() {
    clearReadingHistory();
    setHistory([]);
  }

  function historyDescription(item: ReadingHistoryItem) {
    const cardsText = item.selectedCards.map((card) => `${card.name}${card.orientation}`).join("，");
    return `${item.readerName} · ${cardsText}`;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);
    const readerName = selectedReader ? getReaderPresentation(selectedReader).title : "默认风格";
    startReadingTask(
      {
        readerId,
        question,
        selectedCards,
        result: null,
      },
      readerName,
    );
  }

  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-[0.9fr_minmax(0,1.1fr)]">
      <section className="min-w-0 rounded-3xl border border-white/10 bg-white/[0.06] p-6">
        <p className="text-sm uppercase tracking-[0.2em] text-gold/70">Reading</p>
        <h1 className="mt-3 text-3xl font-semibold text-cream">体验占卜</h1>
        <p className="mt-3 text-sm leading-6 text-cream/60">写下你的问题，选择一种解读风格，再抽出三张牌。</p>

        <form onSubmit={submit} className="mt-6 space-y-5">
          <ReaderPicker readers={readers} value={readerId} onChange={setReaderId} />

          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            required
            placeholder="例如：我和前任还有机会复合吗？"
            className="min-h-32 w-full rounded-2xl border border-white/10 bg-night px-4 py-3 text-cream outline-none focus:border-gold/50"
          />

          <CardSelector cards={cards} value={selectedCards} onChange={setSelectedCards} />
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs leading-5 text-cream/45">
            <p>解读会在本页之外继续进行，切换页面后再回来也能看到结果。</p>
            <button type="button" onClick={clearSavedState} className="rounded-full border border-white/10 px-3 py-1.5 text-cream/60 transition hover:border-gold/30 hover:text-gold">
              清空当前记录
            </button>
          </div>
          <LoadingButton isLoading={isGenerating} loadingText="解读中…">开始解读</LoadingButton>
        </form>

        <HistoryList
          title="最近 10 次占卜"
          emptyText="完成一次解读后，记录会显示在这里。"
          items={history.map((item) => ({
            id: item.id,
            title: item.question || "未填写问题",
            description: historyDescription(item),
            savedAt: item.savedAt,
          }))}
          onSelect={restoreHistoryItem}
          onClear={clearHistory}
        />
      </section>

      <div className="min-w-0 space-y-4">
        {isGenerating ? <div className="rounded-2xl border border-gold/30 bg-gold/10 p-4 text-sm leading-6 text-gold">解读正在进行中。你可以切到其他页面，完成后再回来查看。</div> : null}
        {error ? <div className="rounded-2xl border border-red-300/30 bg-red-500/10 p-4 text-sm text-red-100">{error}</div> : null}
        <ResultPanel title="解读结果" answer={result?.answer ?? ""} documents={result?.knowledge_docs ?? []} sourcesDisplay="summary" />
      </div>
    </div>
  );
}
