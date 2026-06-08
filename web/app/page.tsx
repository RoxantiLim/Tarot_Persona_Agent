import Link from "next/link";
import { FeatureCard } from "@/components/feature-card";

export default function HomePage() {
  return (
    <div className="space-y-12">
      <section className="grid gap-8 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
        <div className="space-y-7">
          <p className="w-fit rounded-full border border-gold/30 bg-gold/10 px-4 py-2 text-sm text-gold">
            私有知识库 · 三牌解读 · 安静提问
          </p>
          <div className="space-y-5">
            <h1 className="max-w-3xl text-5xl font-semibold leading-tight text-cream md:text-7xl">
              把问题放下，让牌面给你一段线索。
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-cream/70">
              查询牌意，抽三张牌，得到一段结合资料与语气风格的解读。
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/reading" className="rounded-full bg-gold px-6 py-3 font-semibold text-ink transition hover:bg-gold/90">
              开始三牌解读
            </Link>
            <Link href="/knowledge" className="rounded-full border border-white/15 px-6 py-3 font-semibold text-cream transition hover:bg-white/10">
              打开知识库助手
            </Link>
          </div>
        </div>
        <div className="rounded-[2rem] border border-white/10 bg-white/[0.06] p-6 shadow-glow">
          <div className="rounded-[1.5rem] border border-gold/20 bg-ink/70 p-6">
            <p className="text-sm uppercase tracking-[0.24em] text-gold/70">Three Card Reading</p>
            <div className="mt-6 grid grid-cols-3 gap-3">
              {["过去", "现在", "可能性"].map((label) => (
                <div key={label} className="min-h-44 rounded-3xl border border-gold/30 bg-gradient-to-br from-wine/80 to-ink p-4">
                  <div className="h-full rounded-2xl border border-white/10 p-4 text-center">
                    <p className="text-xs text-cream/50">{label}</p>
                    <p className="mt-10 text-3xl text-gold">✶</p>
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-6 text-sm leading-6 text-cream/60">
              先写下问题，再选择牌面。解读会留在当前页面，适合边看边整理。
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <FeatureCard title="知识库助手" description="查牌意、主题和出处，适合学习牌面含义。" href="/knowledge" />
        <FeatureCard title="占卜 Agent" description="输入问题，选择风格，体验一次三牌解读。" href="/reading" />
      </section>
    </div>
  );
}
