type LoadingButtonProps = {
  isLoading: boolean;
  loadingText?: string;
  children: React.ReactNode;
};

export function LoadingButton({ isLoading, loadingText = "处理中…", children }: LoadingButtonProps) {
  return (
    <button
      type="submit"
      disabled={isLoading}
      className="rounded-full bg-gold px-6 py-3 font-semibold text-ink transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {isLoading ? loadingText : children}
    </button>
  );
}
