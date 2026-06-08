"use client";

import { getReaderPresentation } from "@/lib/reader-presentations";
import type { Reader } from "@/lib/types";

type ReaderPickerProps = {
  readers: Reader[];
  value: string;
  onChange: (readerId: string) => void;
};

export function ReaderPicker({ readers, value, onChange }: ReaderPickerProps) {
  if (!readers.length) {
    return (
      <div className="rounded-2xl border border-white/10 bg-ink/60 p-4 text-sm text-cream/50">
        正在载入解读风格…
      </div>
    );
  }

  return (
    <fieldset className="space-y-3">
      <legend className="text-sm text-cream/70">解读风格</legend>
      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="解读风格">
        {readers.map((reader) => {
          const presentation = getReaderPresentation(reader);
          const isSelected = reader.reader_id === value;

          return (
            <button
              key={reader.reader_id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => onChange(reader.reader_id)}
              className={`group relative overflow-hidden rounded-3xl border p-4 text-left transition ${
                isSelected
                  ? "border-gold/70 bg-gold/15 shadow-glow"
                  : "border-white/10 bg-white/[0.06] hover:border-gold/30 hover:bg-white/[0.09]"
              }`}
            >
              <div className="flex items-start gap-4">
                <ReaderMotif motif={presentation.motif} selected={isSelected} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`text-base font-semibold ${isSelected ? "text-gold" : "text-cream"}`}>
                      {presentation.title}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${isSelected ? "bg-gold text-ink" : "bg-white/10 text-cream/55"}`}>
                      {presentation.badge}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-cream/60">{presentation.description}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

function ReaderMotif({ motif, selected }: { motif: ReaderPresentationMotif; selected: boolean }) {
  const stroke = selected ? "#d9b56c" : "rgba(245, 234, 215, 0.62)";
  const fill = selected ? "rgba(217, 181, 108, 0.12)" : "rgba(245, 234, 215, 0.05)";

  if (motif === "moon") {
    return (
      <svg className="h-16 w-16 shrink-0" viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r="28" fill={fill} stroke={stroke} strokeWidth="1.5" />
        <path d="M39 17c-8 3-13 10-13 18s5 14 13 16c-3 2-7 3-11 2-10-2-17-11-15-21 2-11 12-18 22-16 2 0 3 1 4 1Z" fill="none" stroke={stroke} strokeWidth="2" />
        <path d="M45 24h6M48 21v6M43 42h5M45.5 39.5v5" stroke={stroke} strokeLinecap="round" strokeWidth="1.6" />
      </svg>
    );
  }

  return (
    <svg className="h-16 w-16 shrink-0" viewBox="0 0 64 64" aria-hidden="true">
      <circle cx="32" cy="32" r="28" fill={fill} stroke={stroke} strokeWidth="1.5" />
      <circle cx="32" cy="32" r="10" fill="none" stroke={stroke} strokeWidth="2" />
      <path d="M32 11v9M32 44v9M11 32h9M44 32h9M17 17l6 6M41 41l6 6M47 17l-6 6M23 41l-6 6" stroke={stroke} strokeLinecap="round" strokeWidth="1.8" />
    </svg>
  );
}

type ReaderPresentationMotif = ReturnType<typeof getReaderPresentation>["motif"];
