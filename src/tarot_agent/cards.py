from __future__ import annotations

MAJOR_ARCANA = [
    ("愚人", "The Fool"),
    ("魔术师", "The Magician"),
    ("女祭司", "The High Priestess"),
    ("皇后", "The Empress"),
    ("皇帝", "The Emperor"),
    ("教皇", "The Hierophant"),
    ("恋人", "The Lovers"),
    ("战车", "The Chariot"),
    ("力量", "Strength"),
    ("隐士", "The Hermit"),
    ("命运之轮", "Wheel of Fortune"),
    ("正义", "Justice"),
    ("倒吊人", "The Hanged Man"),
    ("死神", "Death"),
    ("节制", "Temperance"),
    ("恶魔", "The Devil"),
    ("高塔", "The Tower"),
    ("星星", "The Star"),
    ("月亮", "The Moon"),
    ("太阳", "The Sun"),
    ("审判", "Judgement"),
    ("世界", "The World"),
]

SUITS = {
    "权杖": "Wands",
    "圣杯": "Cups",
    "宝剑": "Swords",
    "星币": "Pentacles",
}

RANKS = [
    ("一", "Ace"),
    ("二", "Two"),
    ("三", "Three"),
    ("四", "Four"),
    ("五", "Five"),
    ("六", "Six"),
    ("七", "Seven"),
    ("八", "Eight"),
    ("九", "Nine"),
    ("十", "Ten"),
    ("侍从", "Page"),
    ("骑士", "Knight"),
    ("皇后", "Queen"),
    ("国王", "King"),
]

MINOR_ARCANA = [
    (f"{suit_cn}{rank_cn}", f"{rank_en} of {suit_en}")
    for suit_cn, suit_en in SUITS.items()
    for rank_cn, rank_en in RANKS
]


def card_display_names() -> list[str]:
    return [f"{cn} / {en}" for cn, en in [*MAJOR_ARCANA, *MINOR_ARCANA]]


def chinese_card_names() -> list[str]:
    return [cn for cn, _ in [*MAJOR_ARCANA, *MINOR_ARCANA]]
