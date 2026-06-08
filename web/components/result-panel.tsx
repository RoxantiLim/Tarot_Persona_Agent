import type { SourceDocument } from "@/lib/types";
import { MarkdownContent } from "@/components/markdown-content";
import { SourceCard } from "@/components/source-card";

type ResultPanelProps = {
  title: string;
  answer: string;
  error?: string;
  documents?: SourceDocument[];
  sourcesDisplay?: "cards" | "summary";
};

function sourceLabel(doc: SourceDocument) {
  return `${doc.source_file} / 第 ${doc.page ?? "?"} 页`;
}

function uniqueSources(documents: SourceDocument[]) {
  const seen = new Set<string>();
  return documents.flatMap((doc) => {
    const label = sourceLabel(doc);
    if (seen.has(label)) {
      return [];
    }
    seen.add(label);
    return [label];
  });
}

export function ResultPanel({ title, answer, error, documents = [], sourcesDisplay = "cards" }: ResultPanelProps) {
  if (!answer && !error && documents.length === 0) {
    return (
      <div className="min-w-0 rounded-3xl border border-white/10 bg-white/[0.04] p-8 text-cream/55">
        结果会显示在这里。输入问题后，先确认内容，再开始查询或解读。
      </div>
    );
  }

  return (
    <section className="min-w-0 space-y-5 overflow-hidden rounded-3xl border border-white/10 bg-white/[0.06] p-6">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-gold/70">{title}</p>
        {error ? <p className="mt-3 rounded-2xl border border-gold/20 bg-gold/10 p-3 text-sm text-gold">{error}</p> : null}
      </div>
      {answer ? <MarkdownContent content={answer} /> : null}
      {documents.length && sourcesDisplay === "summary" ? (
        <details className="group rounded-2xl border border-white/10 bg-ink/50 p-4">
          <summary className="cursor-pointer list-none text-sm font-semibold text-cream/80">
            <span className="text-gold">引用资料</span>
            <span className="ml-2 text-cream/45">共 {uniqueSources(documents).length} 处</span>
            <span className="float-right text-cream/45 transition group-open:rotate-180">⌄</span>
          </summary>
          <ul className="mt-4 space-y-2 text-sm leading-6 text-cream/60">
            {uniqueSources(documents).map((source) => (
              <li key={source} className="break-words [overflow-wrap:anywhere]">
                {source}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {documents.length && sourcesDisplay === "cards" ? (
        <div className="min-w-0 space-y-3">
          <p className="text-sm font-semibold text-cream/80">参考来源</p>
          {documents.map((doc, index) => (
            <SourceCard key={`${doc.source_file}-${doc.page}-${index}`} doc={doc} index={index + 1} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
