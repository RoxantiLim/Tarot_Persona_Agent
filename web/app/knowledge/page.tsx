"use client";

import { FormEvent, useEffect, useState, useSyncExternalStore } from "react";
import { HistoryList } from "@/components/history-list";
import { LoadingButton } from "@/components/loading-button";
import { ResultPanel } from "@/components/result-panel";
import { apiGet } from "@/lib/api";
import {
  clearKnowledgeHistory,
  clearKnowledgeState,
  loadKnowledgeHistory,
  loadKnowledgeState,
  modeLabels,
  modes,
  normalizeReferenceLevel,
  orientations,
  referenceLevels,
  saveKnowledgeState,
  topics,
  type KnowledgeHistoryItem,
  type KnowledgeMode,
  type KnowledgeSavedState,
} from "@/lib/knowledge-storage";
import {
  getKnowledgeTaskServerSnapshot,
  getKnowledgeTaskSnapshot,
  startKnowledgeTask,
  subscribeKnowledgeTask,
} from "@/lib/knowledge-task-store";

export default function KnowledgePage() {
  const [cards, setCards] = useState<string[]>([]);
  const [mode, setMode] = useState<KnowledgeMode>("牌意查询");
  const [cardName, setCardName] = useState("");
  const [orientation, setOrientation] = useState("不限定");
  const [topic, setTopic] = useState("通用");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [result, setResult] = useState<KnowledgeSavedState["result"]>(null);
  const [error, setError] = useState("");
  const [hasRestoredState, setHasRestoredState] = useState(false);
  const [history, setHistory] = useState<KnowledgeHistoryItem[]>([]);
  const taskSnapshot = useSyncExternalStore(subscribeKnowledgeTask, getKnowledgeTaskSnapshot, getKnowledgeTaskServerSnapshot);
  const isQuerying = taskSnapshot.status === "running";

  useEffect(() => {
    apiGet<{ cards: string[] }>("/api/cards")
      .then((payload) => {
        setCards(payload.cards);
        setCardName((currentCardName) => currentCardName || payload.cards[0] || "");
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    const savedState = loadKnowledgeState();
    if (savedState) {
      setMode(savedState.mode);
      setCardName(savedState.cardName);
      setOrientation(savedState.orientation);
      setTopic(savedState.topic);
      setQuery(savedState.query);
      setTopK(normalizeReferenceLevel(savedState.topK));
      setResult(savedState.result);
    }
    setHistory(loadKnowledgeHistory());
    setHasRestoredState(true);
  }, []);

  useEffect(() => {
    if (!hasRestoredState) {
      return;
    }

    saveKnowledgeState({
      mode,
      cardName,
      orientation,
      topic,
      query,
      topK,
      result,
    });
  }, [cardName, hasRestoredState, mode, orientation, query, result, topK, topic]);

  useEffect(() => {
    if (taskSnapshot.status === "idle") {
      return;
    }

    setMode(taskSnapshot.state.mode);
    setCardName(taskSnapshot.state.cardName);
    setOrientation(taskSnapshot.state.orientation);
    setTopic(taskSnapshot.state.topic);
    setQuery(taskSnapshot.state.query);
    setTopK(normalizeReferenceLevel(taskSnapshot.state.topK));

    if (taskSnapshot.status === "running") {
      setResult(null);
      setError("");
      return;
    }

    if (taskSnapshot.status === "success") {
      setResult(taskSnapshot.result);
      setHistory(loadKnowledgeHistory());
      setError("");
      return;
    }

    setResult(null);
    setError(taskSnapshot.message);
  }, [taskSnapshot]);

  function clearSavedState() {
    if (isQuerying) {
      setError("这次查询还在进行中，完成后再清空当前记录。");
      return;
    }

    clearKnowledgeState();
    setMode("牌意查询");
    setCardName(cards[0] ?? "");
    setOrientation("不限定");
    setTopic("通用");
    setQuery("");
    setTopK(5);
    setResult(null);
    setError("");
  }

  function restoreHistoryItem(id: string) {
    if (isQuerying) {
      setError("这次查询还在进行中，完成后再打开历史记录。");
      return;
    }

    const item = history.find((historyItem) => historyItem.id === id);
    if (!item) {
      return;
    }

    setMode(item.mode);
    setCardName(item.cardName);
    setOrientation(item.orientation);
    setTopic(item.topic);
    setQuery(item.query);
    setTopK(normalizeReferenceLevel(item.topK));
    setResult(item.result);
    setError("");
  }

  function clearHistory() {
    clearKnowledgeHistory();
    setHistory([]);
  }

  function historyTitle(item: KnowledgeHistoryItem) {
    if (item.mode === "牌意查询") {
      return [item.cardName, item.orientation, item.topic].filter(Boolean).join(" · ");
    }
    return item.query || modeLabels[item.mode];
  }

  function historyDescription(item: KnowledgeHistoryItem) {
    const sourceCount = item.result?.documents?.length ?? 0;
    const queryText = item.query ? `问题：${item.query}` : "没有补充问题";
    return `${modeLabels[item.mode]} · ${queryText} · ${sourceCount} 个参考来源`;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);
    startKnowledgeTask({
      mode,
      cardName,
      orientation,
      topic,
      query,
      topK,
      result: null,
    });
  }

  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-[0.82fr_minmax(0,1.18fr)]">
      <section className="min-w-0 rounded-3xl border border-white/10 bg-white/[0.06] p-6">
        <p className="text-sm uppercase tracking-[0.2em] text-gold/70">Knowledge</p>
        <h1 className="mt-3 text-3xl font-semibold text-cream">知识库助手</h1>
        <p className="mt-3 text-sm leading-6 text-cream/60">输入牌名、主题，或一段关键词，查看相关解释与出处。</p>

        <form onSubmit={submit} className="mt-6 space-y-5">
          <div className="grid grid-cols-3 gap-2">
            {modes.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setMode(item)}
                className={`rounded-full px-3 py-2 text-sm transition ${mode === item ? "bg-gold text-ink" : "bg-white/10 text-cream/70 hover:bg-white/15"}`}
              >
                {modeLabels[item]}
              </button>
            ))}
          </div>

          {mode === "牌意查询" ? (
            <div className="grid gap-3">
              <select value={cardName} onChange={(event) => setCardName(event.target.value)} className="rounded-xl border border-white/10 bg-night px-3 py-3 text-cream outline-none focus:border-gold/50">
                {cards.map((card) => (
                  <option key={card} value={card}>
                    {card}
                  </option>
                ))}
              </select>
              <div className="grid gap-3 md:grid-cols-2">
                <select value={orientation} onChange={(event) => setOrientation(event.target.value)} className="rounded-xl border border-white/10 bg-night px-3 py-3 text-cream outline-none focus:border-gold/50">
                  {orientations.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
                <select value={topic} onChange={(event) => setTopic(event.target.value)} className="rounded-xl border border-white/10 bg-night px-3 py-3 text-cream outline-none focus:border-gold/50">
                  {topics.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ) : null}

          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={mode === "资料检索" ? "例如：韦斯康提 米兰 公爵 塔罗 历史" : "例如：圣杯六正位在感情复合里怎么理解？"}
            className="min-h-32 w-full rounded-2xl border border-white/10 bg-night px-4 py-3 text-cream outline-none focus:border-gold/50"
          />

          <div className="space-y-3">
            <p className="text-sm text-cream/60">参考范围</p>
            <div className="grid grid-cols-3 gap-2">
              {referenceLevels.map((level) => (
                <button
                  key={level.value}
                  type="button"
                  onClick={() => setTopK(level.value)}
                  className={`rounded-2xl px-3 py-3 text-left transition ${topK === level.value ? "bg-gold text-ink" : "bg-white/10 text-cream/70 hover:bg-white/15"}`}
                >
                  <span className="block text-sm font-semibold">{level.label}</span>
                  <span className={`mt-1 block text-xs ${topK === level.value ? "text-ink/70" : "text-cream/45"}`}>{level.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-xs leading-5 text-cream/45">
            <p>查询会在本页之外继续进行，切换页面后再回来也能看到结果。</p>
            <button type="button" onClick={clearSavedState} className="rounded-full border border-white/10 px-3 py-1.5 text-cream/60 transition hover:border-gold/30 hover:text-gold">
              清空当前记录
            </button>
          </div>

          <LoadingButton isLoading={isQuerying} loadingText="查询中…">开始查询</LoadingButton>
        </form>

        <HistoryList
          title="最近 10 次查询"
          emptyText="完成一次查询后，记录会显示在这里。"
          items={history.map((item) => ({
            id: item.id,
            title: historyTitle(item),
            description: historyDescription(item),
            savedAt: item.savedAt,
          }))}
          onSelect={restoreHistoryItem}
          onClear={clearHistory}
        />
      </section>

      <div className="min-w-0 space-y-4">
        {isQuerying ? <div className="rounded-2xl border border-gold/30 bg-gold/10 p-4 text-sm leading-6 text-gold">查询正在进行中。你可以切到其他页面，完成后再回来查看。</div> : null}
        {error ? <div className="rounded-2xl border border-red-300/30 bg-red-500/10 p-4 text-sm text-red-100">{error}</div> : null}
        <ResultPanel title="查询结果" answer={result?.answer ?? ""} error={result?.error} documents={result?.documents ?? []} />
      </div>
    </div>
  );
}
