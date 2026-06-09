"use client";

import { useEffect, useState, type KeyboardEvent, type MouseEvent, type TouchEvent } from "react";
import { CardImage } from "@/components/card-image";
import { CardPicker } from "@/components/card-picker";
import { randomCardDraw, splitCardName } from "@/lib/card-assets";
import type { CardInput } from "@/lib/types";

type DrawMode = "random" | "manual";

type DrawPanelProps = {
  cards: string[];
  value: CardInput[];
  onChange: (cards: CardInput[]) => void;
  isSubmitting?: boolean;
  submitLabel?: string;
  submittingLabel?: string;
};

const emptyThreeCards: CardInput[] = [
  { name: "", orientation: "正位" },
  { name: "", orientation: "正位" },
  { name: "", orientation: "正位" },
];

export function DrawPanel({ cards, value, onChange, isSubmitting = false, submitLabel = "开始解读", submittingLabel = "解读中…" }: DrawPanelProps) {
  const [mode, setMode] = useState<DrawMode>("random");
  const [manualIndex, setManualIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const normalizedCards = normalizeThreeCards(value);
  const hasSelectedCards = normalizedCards.every((card) => card.name);

  useEffect(() => {
    if (!isAnimating) {
      return;
    }

    const timer = window.setTimeout(() => setIsAnimating(false), 760);
    return () => window.clearTimeout(timer);
  }, [isAnimating]);

  function selectMode(nextMode: DrawMode) {
    setMode(nextMode);
    if (nextMode === "manual" && !hasSelectedCards && cards.length >= 3) {
      onChange(cards.slice(0, 3).map((name) => ({ name, orientation: "正位" })));
    }
  }

  function drawCards() {
    if (!cards.length) {
      return;
    }
    setIsAnimating(true);
    onChange(randomCardDraw(cards, normalizedCards));
  }

  function handleDrawMouseDown(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    drawCards();
  }

  function handleDrawTouchStart(event: TouchEvent<HTMLButtonElement>) {
    event.preventDefault();
    drawCards();
  }

  function handleDrawKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    drawCards();
  }

  function updateCard(index: number, patch: Partial<CardInput>) {
      onChange(normalizedCards.map((card, cardIndex) => (cardIndex === index ? { ...card, ...patch } : card)));
  }

  function goToManualCard(direction: -1 | 1) {
    setManualIndex((currentIndex) => (currentIndex + direction + normalizedCards.length) % normalizedCards.length);
  }

  return (
    <section className="space-y-4" aria-labelledby="draw-panel-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p id="draw-panel-title" className="font-semibold text-cream">
            三张牌
          </p>
          <p className="mt-1 text-sm text-cream/45">先抽牌，也可以录入你已经抽到的牌。</p>
        </div>
        <div className="rounded-full border border-white/10 bg-ink/70 p-1" role="tablist" aria-label="抽牌方式">
          {[
            { id: "random", label: "随机抽牌" },
            { id: "manual", label: "手动录入" },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={mode === item.id}
              onClick={() => selectMode(item.id as DrawMode)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
                mode === item.id ? "bg-gold text-ink" : "text-cream/60 hover:bg-white/10 hover:text-cream"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {mode === "random" ? (
        <div className="rounded-[2rem] border border-white/10 bg-gradient-to-br from-ink/90 to-wine/45 p-5">
          <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <DeckPreview isAnimating={isAnimating} />
            <div className="relative z-20 flex flex-wrap items-center justify-center gap-3 rounded-3xl border border-white/10 bg-ink/85 p-4 shadow-glow lg:justify-start">
              <button
                type="button"
                onMouseDown={handleDrawMouseDown}
                onTouchStart={handleDrawTouchStart}
                onKeyDown={handleDrawKeyDown}
                disabled={!cards.length || isAnimating}
                className="min-w-36 rounded-full border border-gold/45 bg-night px-6 py-3 font-semibold text-gold transition-colors duration-150 hover:bg-gold/10 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-gold/40"
              >
                {hasSelectedCards ? "重新抽三张" : "抽三张"}
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !hasSelectedCards}
                className="min-w-36 rounded-full bg-gold px-6 py-3 font-semibold text-ink shadow-glow transition-colors duration-150 hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-45 focus-visible:ring-2 focus-visible:ring-gold/40"
              >
                {isSubmitting ? submittingLabel : submitLabel}
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {hasSelectedCards
              ? normalizedCards.map((card, index) => <DrawnCard key={`${card.name}-${index}`} card={card} index={index} isAnimating={isAnimating} />)
              : emptyThreeCards.map((_, index) => (
                  <div key={index} className="rounded-3xl border border-white/10 bg-white/[0.04] p-4 text-center">
                    <CardImage mode="back" size="md" className="mx-auto" />
                    <p className="mt-3 text-sm text-cream/45">第 {index + 1} 张</p>
                  </div>
                ))}
          </div>
        </div>
      ) : (
        <div className="grid gap-4">
          <ManualCardEditor
            cards={cards}
            card={normalizedCards[manualIndex]}
            index={manualIndex}
            onChange={(patch) => updateCard(manualIndex, patch)}
            onPrevious={() => goToManualCard(-1)}
            onNext={() => goToManualCard(1)}
            onSelectIndex={setManualIndex}
            selectedCards={normalizedCards}
            isSubmitting={isSubmitting}
            hasSelectedCards={hasSelectedCards}
            submitLabel={submitLabel}
            submittingLabel={submittingLabel}
          />
        </div>
      )}
    </section>
  );
}

function DeckPreview({ isAnimating }: { isAnimating: boolean }) {
  return (
    <div className="pointer-events-none relative mx-auto h-48 w-52" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <CardImage
          key={index}
          mode="back"
          size="lg"
          className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 transition-transform duration-500 motion-reduce:transition-none ${
            isAnimating ? ["-rotate-12 -translate-x-20", "rotate-0 -translate-y-20", "rotate-12 translate-x-4"][index] : ["-rotate-10 -translate-x-16", "rotate-0", "rotate-10 translate-x-16"][index]
          }`}
        />
      ))}
    </div>
  );
}

function DrawnCard({ card, index, isAnimating }: { card: CardInput; index: number; isAnimating: boolean }) {
  const { chineseName, englishName } = splitCardName(card.name);

  return (
    <article
      className={`rounded-3xl border border-gold/20 bg-ink/70 p-4 text-center transition-[opacity,transform] duration-500 motion-reduce:transition-none ${
        isAnimating ? "translate-y-3 opacity-0" : "translate-y-0 opacity-100"
      }`}
      style={{ transitionDelay: `${index * 120}ms` }}
    >
      <CardImage card={card} size="lg" className="mx-auto" />
      <p className="mt-4 text-sm text-gold/70">第 {index + 1} 张 · {card.orientation}</p>
      <h3 className="mt-1 text-lg font-semibold leading-7 text-cream">{chineseName}</h3>
      <p className="mx-auto mt-1 max-w-32 text-wrap text-sm leading-5 text-cream/45">{englishName}</p>
    </article>
  );
}

function ManualCardEditor({
  cards,
  card,
  index,
  onChange,
  onPrevious,
  onNext,
  onSelectIndex,
  selectedCards,
  isSubmitting,
  hasSelectedCards,
  submitLabel,
  submittingLabel,
}: {
  cards: string[];
  card: CardInput;
  index: number;
  onChange: (patch: Partial<CardInput>) => void;
  onPrevious: () => void;
  onNext: () => void;
  onSelectIndex: (index: number) => void;
  selectedCards: CardInput[];
  isSubmitting: boolean;
  hasSelectedCards: boolean;
  submitLabel: string;
  submittingLabel: string;
}) {
  return (
    <article className="rounded-3xl border border-white/10 bg-ink/60 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button type="button" onClick={onPrevious} className="rounded-full border border-white/10 px-3 py-2 text-sm text-cream/65 transition hover:border-gold/30 hover:text-gold focus-visible:ring-2 focus-visible:ring-gold/30">
            上一张
          </button>
          <p className="rounded-full bg-gold px-4 py-2 text-sm font-semibold text-ink">第 {index + 1} 张</p>
          <button type="button" onClick={onNext} className="rounded-full border border-white/10 px-3 py-2 text-sm text-cream/65 transition hover:border-gold/30 hover:text-gold focus-visible:ring-2 focus-visible:ring-gold/30">
            下一张
          </button>
        </div>
        <div className="rounded-full border border-white/10 bg-night p-1" aria-label={`第 ${index + 1} 张正逆位`}>
          {(["正位", "逆位"] as const).map((orientation) => (
            <button
              key={orientation}
              type="button"
              onClick={() => onChange({ orientation })}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
                card.orientation === orientation ? "bg-gold text-ink" : "text-cream/60 hover:bg-white/10 hover:text-cream"
              }`}
            >
              {orientation}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[11rem_minmax(0,1fr)] lg:items-start">
        <div className="flex justify-center lg:justify-start">
          <CardImage card={card.name ? card : undefined} mode={card.name ? "face" : "back"} size="lg" className="mx-auto lg:mx-0" />
        </div>
        <div className="space-y-3">
          <CardPicker cards={cards} value={card.name} onChange={(name) => onChange({ name })} label={`选择第 ${index + 1} 张牌`} id={`reading-card-${index}`} layout="compact" />
          <div className="px-4">
            <button
              type="submit"
              disabled={isSubmitting || !hasSelectedCards}
              className="w-full rounded-full bg-gold px-6 py-3 font-semibold text-ink shadow-glow transition-colors duration-150 hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-gold/40"
            >
              {isSubmitting ? submittingLabel : submitLabel}
            </button>
          </div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {selectedCards.map((selectedCard, selectedIndex) => {
          const { chineseName } = splitCardName(selectedCard.name || `第 ${selectedIndex + 1} 张`);
          const isActive = selectedIndex === index;

          return (
            <button
              key={selectedIndex}
              type="button"
              onClick={() => onSelectIndex(selectedIndex)}
              className={`rounded-2xl border p-3 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
                isActive ? "border-gold/70 bg-gold/15 text-gold" : "border-white/10 bg-white/[0.04] text-cream/55 hover:border-gold/30 hover:text-cream"
              }`}
            >
              <span className="block text-xs">第 {selectedIndex + 1} 张</span>
              <span className="mt-1 block truncate text-sm font-semibold">{selectedCard.name ? chineseName : "未选择"}</span>
            </button>
          );
        })}
      </div>
    </article>
  );
}

function normalizeThreeCards(cards: CardInput[]) {
  return [0, 1, 2].map((index) => cards[index] ?? emptyThreeCards[index]);
}
