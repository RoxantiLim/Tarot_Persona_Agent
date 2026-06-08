import type { SourceDocument } from "@/lib/types";

export function SourceCard({ doc, index }: { doc: SourceDocument; index: number }) {
  return (
    <article className="min-w-0 rounded-2xl border border-white/10 bg-ink/60 p-4">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
        <p className="min-w-0 break-words text-sm font-semibold text-gold [overflow-wrap:anywhere]">
          {index}. {doc.source_file} / 第 {doc.page ?? "?"} 页
        </p>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-cream/60">
          {doc.quality_status}
        </span>
      </div>
      <p className="mt-3 line-clamp-5 whitespace-pre-wrap break-words text-sm leading-6 text-cream/65 [overflow-wrap:anywhere]">{doc.content}</p>
    </article>
  );
}
