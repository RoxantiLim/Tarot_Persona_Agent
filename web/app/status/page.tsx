"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

export default function StatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<HealthResponse>("/api/health")
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section className="rounded-3xl border border-white/10 bg-white/[0.06] p-6">
        <p className="text-sm uppercase tracking-[0.2em] text-gold/70">Status</p>
        <h1 className="mt-3 text-3xl font-semibold text-cream">准备状态</h1>
        <p className="mt-3 text-sm leading-6 text-cream/60">检查查询和解读功能是否准备好。</p>
      </section>

      {error ? (
        <div className="rounded-3xl border border-red-300/30 bg-red-500/10 p-6 text-red-100">
          还没有连上本地服务：{error}
        </div>
      ) : null}

      {health ? (
        <section className="grid gap-4 md:grid-cols-2">
          <StatusItem label="本地服务" value={health.ok ? "已连接" : "异常"} />
          <StatusItem label="资料库" value={health.index_exists ? "已准备" : "未准备"} />
          <StatusItem label="查询方式" value={health.retrieval_mode} />
          <StatusItem label="资料引擎" value={health.vector_store_backend} />
          <StatusItem label="匹配模型" value={health.embedding_model} />
          <StatusItem label="解读模型" value={health.llm_model} />
          <StatusItem label="牌数" value={`${health.cards_count} 张`} />
          <StatusItem label="解读风格" value={`${health.readers_count} 个`} />
        </section>
      ) : !error ? (
        <div className="rounded-3xl border border-white/10 bg-white/[0.06] p-6 text-cream/60">正在检查…</div>
      ) : null}
    </div>
  );
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-ink/60 p-5">
      <p className="text-sm text-cream/50">{label}</p>
      <p className="mt-2 text-lg font-semibold text-cream">{value}</p>
    </div>
  );
}
