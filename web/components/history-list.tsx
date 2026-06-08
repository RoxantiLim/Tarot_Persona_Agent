type HistoryListItem = {
  id: string;
  title: string;
  description: string;
  savedAt: string;
};

type HistoryListProps = {
  title: string;
  emptyText: string;
  items: HistoryListItem[];
  onSelect: (id: string) => void;
  onClear: () => void;
};

const historyTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function formatHistoryTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return historyTimeFormatter.format(date);
}

export function HistoryList({ title, emptyText, items, onSelect, onClear }: HistoryListProps) {
  return (
    <section className="mt-6 border-t border-white/10 pt-6">
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold text-cream">{title}</p>
        {items.length ? (
          <button type="button" onClick={onClear} className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-cream/60 transition hover:border-gold/30 hover:text-gold">
            清空历史
          </button>
        ) : null}
      </div>

      {items.length ? (
        <div className="mt-3 space-y-2">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              className="w-full rounded-2xl border border-white/10 bg-ink/50 p-4 text-left transition hover:border-gold/30 hover:bg-white/[0.07]"
            >
              <span className="flex items-center justify-between gap-3">
                <span className="line-clamp-1 text-sm font-semibold text-cream">{item.title}</span>
                <span className="shrink-0 text-xs text-cream/40">{formatHistoryTime(item.savedAt)}</span>
              </span>
              <span className="mt-2 line-clamp-2 block text-xs leading-5 text-cream/55">{item.description}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-2xl border border-white/10 bg-ink/40 p-4 text-sm leading-6 text-cream/50">{emptyText}</p>
      )}
    </section>
  );
}
