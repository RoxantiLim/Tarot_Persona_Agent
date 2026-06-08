"use client";

import type { CardInput } from "@/lib/types";

type CardSelectorProps = {
  cards: string[];
  value: CardInput[];
  onChange: (cards: CardInput[]) => void;
};

export function CardSelector({ cards, value, onChange }: CardSelectorProps) {
  function updateCard(index: number, patch: Partial<CardInput>) {
    onChange(value.map((card, cardIndex) => (cardIndex === index ? { ...card, ...patch } : card)));
  }

  function randomDraw() {
    const shuffled = [...cards].sort(() => Math.random() - 0.5).slice(0, 3);
    onChange(shuffled.map((name) => ({ name, orientation: Math.random() > 0.5 ? "正位" : "逆位" })));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold text-cream">三张牌</p>
        <button type="button" onClick={randomDraw} className="rounded-full border border-gold/30 px-4 py-2 text-sm text-gold hover:bg-gold/10">
          随机抽三张
        </button>
      </div>
      <div className="grid gap-3">
        {value.map((card, index) => (
          <div key={index} className="rounded-2xl border border-white/10 bg-ink/60 p-4">
            <p className="mb-3 text-sm text-cream/50">第 {index + 1} 张</p>
            <div className="grid gap-3 md:grid-cols-[1fr_8rem]">
              <select
                value={card.name}
                onChange={(event) => updateCard(index, { name: event.target.value })}
                className="rounded-xl border border-white/10 bg-night px-3 py-3 text-cream outline-none focus:border-gold/50"
              >
                {cards.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <select
                value={card.orientation}
                onChange={(event) => updateCard(index, { orientation: event.target.value as CardInput["orientation"] })}
                className="rounded-xl border border-white/10 bg-night px-3 py-3 text-cream outline-none focus:border-gold/50"
              >
                <option value="正位">正位</option>
                <option value="逆位">逆位</option>
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
