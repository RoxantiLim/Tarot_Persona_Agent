import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownContentProps = {
  content: string;
};

const markdownComponents: Components = {
  h1({ children }) {
    return <h1 className="mt-8 text-2xl font-semibold leading-9 text-cream first:mt-0">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="mt-7 text-xl font-semibold leading-8 text-cream first:mt-0">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="mt-6 text-lg font-semibold leading-8 text-gold first:mt-0">{children}</h3>;
  },
  p({ children }) {
    return <p className="my-4 leading-8 text-cream/85">{children}</p>;
  },
  strong({ children }) {
    return <strong className="font-semibold text-gold">{children}</strong>;
  },
  ul({ children }) {
    return <ul className="my-4 list-disc space-y-2 pl-6 leading-8 text-cream/85">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="my-4 list-decimal space-y-2 pl-6 leading-8 text-cream/85">{children}</ol>;
  },
  li({ children }) {
    return <li className="pl-1">{children}</li>;
  },
  blockquote({ children }) {
    return <blockquote className="my-5 border-l-2 border-gold/50 bg-gold/10 py-3 pl-4 pr-3 text-cream/75">{children}</blockquote>;
  },
  table({ children }) {
    return (
      <div className="my-5 max-w-full overflow-x-auto rounded-2xl border border-white/10">
        <table className="w-full min-w-[36rem] border-collapse text-left text-sm text-cream/80">{children}</table>
      </div>
    );
  },
  thead({ children }) {
    return <thead className="bg-gold/10 text-gold">{children}</thead>;
  },
  th({ children }) {
    return <th className="border-b border-white/10 px-4 py-3 font-semibold">{children}</th>;
  },
  td({ children }) {
    return <td className="border-t border-white/10 px-4 py-3 align-top leading-6">{children}</td>;
  },
  code({ children, className }) {
    const isBlock = Boolean(className);
    if (isBlock) {
      return <code className="block overflow-x-auto whitespace-pre rounded-2xl bg-ink/80 p-4 text-sm leading-6 text-cream/80">{children}</code>;
    }
    return <code className="rounded-md bg-ink/80 px-1.5 py-0.5 text-sm text-gold">{children}</code>;
  },
  pre({ children }) {
    return <pre className="my-5 max-w-full overflow-x-auto">{children}</pre>;
  },
  a({ children, href }) {
    return (
      <a href={href} className="text-gold underline decoration-gold/40 underline-offset-4 hover:decoration-gold">
        {children}
      </a>
    );
  },
  hr() {
    return <hr className="my-7 border-white/10" />;
  },
};

export function MarkdownContent({ content }: MarkdownContentProps) {
  return (
    <div className="max-w-3xl break-words text-base text-cream/85 [overflow-wrap:anywhere] md:text-[1.05rem]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents} skipHtml>
        {content}
      </ReactMarkdown>
    </div>
  );
}
