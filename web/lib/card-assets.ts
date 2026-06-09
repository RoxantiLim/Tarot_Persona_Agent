import type { CardInput } from "@/lib/types";

export const cardBackPath = "/cards/CardBacks.png";

const majorArcanaFiles: Record<string, string> = {
  愚人: "00-TheFool.png",
  魔术师: "01-TheMagician.png",
  女祭司: "02-TheHighPriestess.png",
  皇后: "03-TheEmpress.png",
  皇帝: "04-TheEmperor.png",
  教皇: "05-TheHierophant.png",
  恋人: "06-TheLovers.png",
  战车: "07-TheChariot.png",
  力量: "08-Strength.png",
  隐士: "09-TheHermit.png",
  命运之轮: "10-WheelOfFortune.png",
  正义: "11-Justice.png",
  倒吊人: "12-TheHangedMan.png",
  死神: "13-Death.png",
  节制: "14-Temperance.png",
  恶魔: "15-TheDevil.png",
  高塔: "16-TheTower.png",
  星星: "17-TheStar.png",
  月亮: "18-TheMoon.png",
  太阳: "19-TheSun.png",
  审判: "20-Judgement.png",
  世界: "21-TheWorld.png",
};

const suitFiles: Record<string, string> = {
  权杖: "Wands",
  圣杯: "Cups",
  宝剑: "Swords",
  星币: "Pentacles",
};

const rankFiles: Record<string, string> = {
  一: "01",
  二: "02",
  三: "03",
  四: "04",
  五: "05",
  六: "06",
  七: "07",
  八: "08",
  九: "09",
  十: "10",
  侍从: "11",
  骑士: "12",
  皇后: "13",
  国王: "14",
};

export function splitCardName(cardName: string) {
  const [chineseName = cardName, englishName = ""] = cardName.split(" / ");
  return {
    chineseName: chineseName.trim(),
    englishName: englishName.trim(),
  };
}

export function cardImagePath(cardName: string) {
  const { chineseName } = splitCardName(cardName);
  const majorFile = majorArcanaFiles[chineseName];

  if (majorFile) {
    return `/cards/${majorFile}`;
  }

  for (const [suitName, suitFile] of Object.entries(suitFiles)) {
    if (!chineseName.startsWith(suitName)) {
      continue;
    }

    const rankName = chineseName.slice(suitName.length);
    const rankFile = rankFiles[rankName];
    if (rankFile) {
      return `/cards/${suitFile}${rankFile}.png`;
    }
  }

  return cardBackPath;
}

export function cardSearchText(cardName: string) {
  const { chineseName, englishName } = splitCardName(cardName);
  return `${chineseName} ${englishName}`.toLowerCase();
}

export function randomCardDraw(cards: string[], previousCards: CardInput[] = []): CardInput[] {
  const shuffled = [...cards];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }

  const draw = shuffled
    .map((name) => {
      const orientation: CardInput["orientation"] = Math.random() > 0.5 ? "正位" : "逆位";
      return { name, orientation };
    })
    .slice(0, 3);

  const isSameDraw = draw.every((card, index) => card.name === previousCards[index]?.name);
  if (!isSameDraw || cards.length <= 3) {
    return draw;
  }

  return cards.slice(3, 6).map((name) => {
    const orientation: CardInput["orientation"] = Math.random() > 0.5 ? "正位" : "逆位";
    return { name, orientation };
  });
}
