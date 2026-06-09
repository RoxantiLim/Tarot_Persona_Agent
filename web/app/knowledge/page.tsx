"use client";

import { FormEvent, useEffect, useState, useSyncExternalStore } from "react";
import { CardImage } from "@/components/card-image";
import { CardPicker } from "@/components/card-picker";
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

const modeDescriptions: Record<KnowledgeMode, string> = {
  牌意查询: "围绕一张牌理解含义",
  主题学习: "按主题整理学习笔记",
  资料检索: "直接查找资料出处",
};

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
          <div className="grid gap-3 md:grid-cols-3" role="tablist" aria-label="知识库任务">
            {modes.map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={mode === item}
                onClick={() => setMode(item)}
                className={`rounded-3xl border p-4 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
                  mode === item ? "border-gold/70 bg-gold/15 text-gold" : "border-white/10 bg-white/[0.06] text-cream/70 hover:border-gold/30 hover:bg-white/[0.09]"
                }`}
              >
                <span className="block text-base font-semibold">{modeLabels[item]}</span>
                <span className={`mt-2 block text-sm leading-6 ${mode === item ? "text-gold/75" : "text-cream/45"}`}>{modeDescriptions[item]}</span>
              </button>
            ))}
          </div>

          {mode === "牌意查询" ? (
            <div className="space-y-4">
              <div className="grid gap-4 rounded-3xl border border-white/10 bg-ink/60 p-4 md:grid-cols-[11rem_minmax(0,1fr)] md:items-start">
                <div className="flex justify-center md:justify-start">
                  <CardImage card={cardName ? { name: cardName, orientation: orientation === "逆位" ? "逆位" : "正位" } : undefined} mode={cardName ? "face" : "back"} size="lg" className="mx-auto md:mx-0" />
                </div>
                <div className="space-y-3">
                  <CardPicker cards={cards} value={cardName} onChange={setCardName} label="选择要查询的牌" id="knowledge-card" layout="compact" />
                  <div className="px-4">
                    <button
                      type="submit"
                      disabled={isQuerying}
                      className="w-full rounded-full bg-gold px-6 py-3 font-semibold text-ink shadow-glow transition-colors duration-150 hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-gold/40"
                    >
                      {isQuerying ? "查询中…" : "开始查询"}
                    </button>
                  </div>
                </div>
              </div>
              <ChoiceGroup label="正逆位" value={orientation} options={orientations} onChange={setOrientation} />
              <ChoiceGroup label="主题" value={topic} options={topics} onChange={setTopic} />
            </div>
          ) : null}

          {mode === "主题学习" ? <ChoiceGroup label="学习主题" value={topic} options={topics} onChange={setTopic} /> : null}

          <label className="block space-y-2 text-sm text-cream/70">
            {mode === "资料检索" ? "搜索关键词" : mode === "主题学习" ? "补充关键词" : "补充问题"}
            <textarea
              name="knowledge-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={mode === "资料检索" ? "例如：韦斯康提 米兰 公爵 塔罗 历史…" : mode === "主题学习" ? "例如：宫廷牌、四元素、关系牌阵…" : "例如：圣杯六正位在感情复合里怎么理解…"}
              autoComplete="off"
              className="min-h-32 w-full rounded-2xl border border-white/10 bg-night px-4 py-3 text-cream outline-none transition-colors duration-150 placeholder:text-cream/30 focus-visible:border-gold/60 focus-visible:ring-2 focus-visible:ring-gold/20"
            />
          </label>

          <div className="space-y-3">
            <p className="text-sm text-cream/60">参考范围</p>
            <div className="grid grid-cols-3 gap-2">
              {referenceLevels.map((level) => (
                <button
                  key={level.value}
                  type="button"
                  onClick={() => setTopK(level.value)}
                  className={`rounded-2xl border px-3 py-3 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
                    topK === level.value ? "border-gold/70 bg-gold/15 text-gold" : "border-white/10 bg-white/[0.06] text-cream/70 hover:border-gold/30 hover:bg-white/[0.09]"
                  }`}
                >
                  <span className="block text-sm font-semibold">{level.label}</span>
                  <span className={`mt-1 block text-xs ${topK === level.value ? "text-gold/75" : "text-cream/45"}`}>{level.description}</span>
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

          {mode !== "牌意查询" ? <LoadingButton isLoading={isQuerying} loadingText="查询中…">开始查询</LoadingButton> : null}
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

function ChoiceGroup({ label, value, options, onChange }: { label: string; value: string; options: readonly string[]; onChange: (value: string) => void }) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm text-cream/60">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={`rounded-full border px-4 py-2 text-sm font-semibold transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
              value === option ? "border-gold/70 bg-gold text-ink" : "border-white/10 bg-white/[0.06] text-cream/65 hover:border-gold/30 hover:bg-white/[0.09] hover:text-cream"
            }`}
          >
            {option}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
