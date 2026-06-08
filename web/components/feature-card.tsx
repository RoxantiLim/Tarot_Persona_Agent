import Link from "next/link";

type FeatureCardProps = {
  title: string;
  description: string;
  href: string;
};

export function FeatureCard({ title, description, href }: FeatureCardProps) {
  return (
    <Link
      href={href}
      className="group rounded-3xl border border-white/10 bg-white/[0.06] p-6 transition hover:-translate-y-1 hover:border-gold/40 hover:bg-white/[0.09]"
    >
      <p className="text-xl font-semibold text-cream">{title}</p>
      <p className="mt-3 text-sm leading-6 text-cream/60">{description}</p>
      <p className="mt-5 text-sm font-semibold text-gold">进入 →</p>
    </Link>
  );
}
