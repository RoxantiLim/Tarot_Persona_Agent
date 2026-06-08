import type { Reader } from "@/lib/types";

export type ReaderPresentation = {
  title: string;
  badge: string;
  description: string;
  motif: "sun" | "moon";
};

const readerPresentations: Record<string, Omit<ReaderPresentation, "description">> = {
  tarotist_1: {
    title: "清晰判断",
    badge: "直接",
    motif: "sun",
  },
  tarotist_2: {
    title: "细腻陪伴",
    badge: "温和",
    motif: "moon",
  },
};

export function getReaderPresentation(reader: Reader): ReaderPresentation {
  const presentation = readerPresentations[reader.reader_id];

  return {
    title: presentation?.title ?? reader.display_name,
    badge: presentation?.badge ?? "默认",
    motif: presentation?.motif ?? "sun",
    description: reader.tone,
  };
}
