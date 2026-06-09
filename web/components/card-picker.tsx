"use client";

import { useEffect, useMemo, useState } from "react";
import { CardImage } from "@/components/card-image";
import { cardSearchText, splitCardName } from "@/lib/card-assets";

type CardPickerProps = {
  cards: string[];
  value: string;
  onChange: (cardName: string) => void;
  label: string;
  id: string;
  layout?: "full" | "compact";
};

export function CardPicker({ cards, value, onChange, label, id, layout = "full" }: CardPickerProps) {
  if (layout === "compact") {
    return <CompactCardPicker cards={cards} value={value} onChange={onChange} label={label} id={id} />;
  }

  return <FullCardPicker cards={cards} value={value} onChange={onChange} label={label} id={id} />;
}

function FullCardPicker({ cards, value, onChange, label, id }: Omit<CardPickerProps, "layout">) {
  const [query, setQuery] = useState("");
  const [showAllCards, setShowAllCards] = useState(false);
  const selectedCard = value || cards[0] || "";
  const selectedNames = splitCardName(selectedCard);
  const normalizedQuery = query.trim().toLowerCase();
  const visibleCards = useMemo(() => {
    const pool = normalizedQuery ? cards.filter((card) => cardSearchText(card).includes(normalizedQuery)) : cards;
    if (showAllCards || normalizedQuery) {
      return pool;
    }
    return pool.slice(0, 12);
  }, [cards, normalizedQuery, showAllCards]);

  return (
    <div className="space-y-4 rounded-3xl border border-white/10 bg-ink/60 p-4">
        <div className="flex min-w-0 items-center gap-3">
          <CardImage card={{ name: selectedCard, orientation: "正位" }} size="md" />
          <div className="min-w-0 flex-1">
            <label htmlFor={id} className="text-sm text-cream/60">
              {label}
            </label>
            <p className="mt-1 truncate text-lg font-semibold text-cream">{selectedNames.chineseName || "选择一张牌"}</p>
            {selectedNames.englishName ? <p className="truncate text-sm text-cream/45">{selectedNames.englishName}</p> : null}
          </div>
        </div>

      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
        <input
          id={id}
          name={id}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索中文或英文牌名…"
          autoComplete="off"
          className="w-full min-w-0 rounded-2xl border border-white/10 bg-night px-4 py-3 text-cream outline-none transition-colors duration-150 placeholder:text-cream/30 focus-visible:border-gold/60 focus-visible:ring-2 focus-visible:ring-gold/20"
        />
        <button
          type="button"
          onClick={() => setShowAllCards((current) => !current)}
          className="rounded-2xl border border-gold/30 px-4 py-3 text-sm font-semibold text-gold transition-colors duration-150 hover:bg-gold/10 focus-visible:ring-2 focus-visible:ring-gold/30"
        >
          {showAllCards ? "收起" : "浏览全部"}
        </button>
      </div>

      <div className="grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
        {visibleCards.map((card) => {
          const names = splitCardName(card);
          const isSelected = card === selectedCard;

          return (
            <button
              key={card}
              type="button"
              onClick={() => onChange(card)}
              className={`flex min-w-0 items-center gap-3 rounded-2xl border px-3 py-2 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
                isSelected ? "border-gold/70 bg-gold/15 text-gold" : "border-white/10 bg-white/[0.04] text-cream/70 hover:border-gold/30 hover:bg-white/[0.08]"
              }`}
            >
              <CardImage card={{ name: card, orientation: "正位" }} size="sm" className="h-14 w-9 rounded-lg shadow-none" />
              <span className="min-w-0">
                <span className="block text-sm font-semibold leading-5">{names.chineseName}</span>
                <span className="block text-xs leading-4 text-cream/45">{names.englishName}</span>
              </span>
            </button>
          );
        })}
      </div>

      {!visibleCards.length ? <p className="rounded-2xl bg-white/[0.04] p-3 text-sm text-cream/45">没有找到这张牌，换个关键词试试。</p> : null}
    </div>
  );
}

function CompactCardPicker({ cards, value, onChange, label, id }: Omit<CardPickerProps, "layout">) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selectedCard = value || cards[0] || "";
  const selectedNames = splitCardName(selectedCard);
  const normalizedQuery = query.trim().toLowerCase();
  const visibleCards = useMemo(() => {
    return normalizedQuery ? cards.filter((card) => cardSearchText(card).includes(normalizedQuery)) : cards;
  }, [cards, normalizedQuery]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function closeOnEscape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isOpen]);

  function chooseCard(card: string) {
    onChange(card);
    setQuery("");
    setIsOpen(false);
  }

  return (
    <div className="min-h-32 rounded-3xl border border-white/10 bg-ink/60 p-4">
      <div className="grid min-h-24 grid-cols-1 items-center gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm text-cream/60">{label}</p>
          <p className="mt-1 truncate text-xl font-semibold leading-7 text-cream">{selectedNames.chineseName || "未选择"}</p>
          {selectedNames.englishName ? <p className="truncate text-sm leading-5 text-cream/45">{selectedNames.englishName}</p> : null}
        </div>
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="w-full min-w-0 max-w-full shrink-0 justify-self-stretch rounded-full bg-gold px-5 py-3 font-semibold text-ink transition-colors duration-150 hover:bg-gold/90 focus-visible:ring-2 focus-visible:ring-gold/40"
        >
          选择牌面
        </button>
      </div>

      {isOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby={`${id}-dialog-title`}>
          <div className="max-h-[88vh] w-full max-w-5xl overflow-hidden rounded-[2rem] border border-white/10 bg-night shadow-glow">
            <div className="border-b border-white/10 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p id={`${id}-dialog-title`} className="text-2xl font-semibold text-cream">
                    选择牌面
                  </p>
                  <p className="mt-1 text-sm text-cream/45">可以直接浏览，也可以搜索中文或英文牌名。</p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-cream/65 transition-colors duration-150 hover:border-gold/30 hover:text-gold focus-visible:ring-2 focus-visible:ring-gold/30"
                >
                  关闭
                </button>
              </div>
              <input
                id={id}
                name={id}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索牌名…"
                autoComplete="off"
                className="mt-4 w-full rounded-2xl border border-white/10 bg-ink px-4 py-3 text-cream outline-none transition-colors duration-150 placeholder:text-cream/30 focus-visible:border-gold/60 focus-visible:ring-2 focus-visible:ring-gold/20"
              />
            </div>

            <div className="max-h-[62vh] overflow-y-auto p-5">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {visibleCards.map((card) => {
                  const names = splitCardName(card);
                  const isSelected = card === selectedCard;

                  return (
                    <button
                      key={card}
                      type="button"
                      onClick={() => chooseCard(card)}
                      className={`flex min-w-0 items-center gap-3 rounded-3xl border p-3 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-gold/30 ${
                        isSelected ? "border-gold/70 bg-gold/15 text-gold" : "border-white/10 bg-white/[0.04] text-cream/75 hover:border-gold/30 hover:bg-white/[0.08]"
                      }`}
                    >
                      <CardImage card={{ name: card, orientation: "正位" }} size="sm" className="h-20 w-14 rounded-xl shadow-none" />
                      <span className="min-w-0">
                        <span className="block text-base font-semibold leading-6">{names.chineseName}</span>
                        <span className="block break-words text-sm leading-5 text-cream/45">{names.englishName}</span>
                      </span>
                    </button>
                  );
                })}
              </div>

              {!visibleCards.length ? <p className="rounded-2xl bg-white/[0.04] p-4 text-sm text-cream/45">没有找到这张牌，换个关键词试试。</p> : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
