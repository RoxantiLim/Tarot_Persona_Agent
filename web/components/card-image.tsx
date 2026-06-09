"use client";

import { useState } from "react";
import { cardBackPath, cardImagePath, splitCardName } from "@/lib/card-assets";
import type { CardInput } from "@/lib/types";

type CardImageProps = {
  card?: CardInput;
  mode?: "face" | "back";
  size?: "sm" | "md" | "lg";
  className?: string;
};

const sizeClasses = {
  sm: "h-24 w-16 rounded-xl",
  md: "h-40 w-28 rounded-2xl",
  lg: "h-60 w-40 rounded-3xl",
};

export function CardImage({ card, mode = "face", size = "md", className = "" }: CardImageProps) {
  const [hasError, setHasError] = useState(false);
  const showBack = mode === "back" || !card?.name;
  const src = showBack ? cardBackPath : cardImagePath(card.name);
  const { chineseName, englishName } = splitCardName(card?.name ?? "塔罗牌");
  const alt = showBack ? "塔罗牌背" : `${chineseName}${englishName ? ` / ${englishName}` : ""}${card?.orientation ? `，${card.orientation}` : ""}`;
  const rotateClass = !showBack && card?.orientation === "逆位" ? "rotate-180" : "";

  if (hasError) {
    return (
      <div
        className={`${sizeClasses[size]} ${className} flex shrink-0 items-center justify-center border border-gold/25 bg-gradient-to-br from-wine/80 to-ink p-3 text-center shadow-glow`}
        aria-label={alt}
        role="img"
      >
        <span className="text-xs leading-5 text-gold/80">{showBack ? "牌背" : chineseName}</span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      width={size === "lg" ? 160 : size === "md" ? 112 : 64}
      height={size === "lg" ? 240 : size === "md" ? 160 : 96}
      loading="lazy"
      onError={() => setHasError(true)}
      className={`${sizeClasses[size]} ${className} ${rotateClass} shrink-0 border border-gold/20 bg-ink object-cover shadow-glow transition-transform duration-500 motion-reduce:transition-none`}
    />
  );
}
