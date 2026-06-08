import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tarot Persona",
  description: "塔罗知识库与三牌解读",
};

const navItems = [
  { href: "/", label: "首页" },
  { href: "/knowledge", label: "知识库助手" },
  { href: "/reading", label: "体验占卜" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="min-h-screen">
          <header className="sticky top-0 z-30 border-b border-white/10 bg-ink/80 backdrop-blur-xl">
            <nav className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
              <Link href="/" className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-2xl border border-gold/40 bg-gold/10 text-gold shadow-glow">
                  ✦
                </span>
                <span>
                  <span className="block text-sm uppercase tracking-[0.28em] text-gold/80">Tarot</span>
                  <span className="block text-base font-semibold text-cream">Persona</span>
                </span>
              </Link>
              <div className="hidden items-center gap-2 md:flex">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="rounded-full px-4 py-2 text-sm text-cream/70 transition hover:bg-white/10 hover:text-cream"
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
              <Link
                href="/status"
                aria-label="查看运行状态"
                title="运行状态"
                className="grid h-9 w-9 place-items-center rounded-full border border-white/10 text-sm font-semibold text-cream/60 transition hover:border-gold/30 hover:bg-white/10 hover:text-gold"
              >
                !
              </Link>
            </nav>
          </header>
          <main className="mx-auto max-w-6xl px-5 py-10">{children}</main>
        </div>
      </body>
    </html>
  );
}
