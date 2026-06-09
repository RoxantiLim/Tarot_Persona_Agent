import type { Reader } from "@/lib/types";

export type ReaderPresentation = {
  title: string;
  badge: string;
  description: string;
  motif: "sun" | "moon";
};

const readerPresentations: Record<string, ReaderPresentation> = {
  tarotist_1: {
    title: "日轮直断",
    badge: "明晰",
    description: "适合想要看清趋势、获得明确提醒的问题。会先揭示牌面主线，再把判断落到现实处境里。",
    motif: "sun",
  },
  tarotist_2: {
    title: "月相审度",
    badge: "审慎",
    description: "适合需要判断时机、状态和可能性的问题。会反映事件的核心，给出繁杂外表下精准的结论。",
    motif: "moon",
  },
};

export function getReaderPresentation(reader: Reader): ReaderPresentation {
  const presentation = readerPresentations[reader.reader_id];

  return {
    title: presentation?.title ?? reader.display_name,
    badge: presentation?.badge ?? "默认",
    motif: presentation?.motif ?? "sun",
    description: presentation?.description ?? "根据当前风格画像生成解读。",
  };
}
