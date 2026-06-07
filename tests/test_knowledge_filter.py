from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.tarot_agent.knowledge_filter import (
    assess_chunk_quality,
    list_filter_overrides,
    load_filter_overrides,
    set_filter_override,
)
from src.tarot_agent.pdf_ingest import split_page_into_chunks


class KnowledgeFilterTests(unittest.TestCase):
    def test_excludes_table_of_contents(self) -> None:
        quality = assess_chunk_quality(
            "Table of Contents\nIntroduction\nChapter 1 - History\nChapter 2 - Symbols"
        )
        self.assertEqual("exclude", quality.status)
        self.assertIn("table_of_contents", quality.reasons)

    def test_excludes_dotted_table_of_contents_continuation(self) -> None:
        quality = assess_chunk_quality(
            "圣杯侍卫 ........................................ 49\n"
            "圣杯骑士 ........................................ 51\n"
            "圣杯皇后 ........................................ 53\n"
            "圣杯国王 ........................................ 55"
        )
        self.assertEqual("exclude", quality.status)
        self.assertIn("table_of_contents", quality.reasons)

    def test_excludes_uppercase_title_page(self) -> None:
        quality = assess_chunk_quality(
            "THE TAROT\nHISTORY\nSYMBOLISM, AND\nDIVINATION\nROBERT M. PLACE\nPENGUIN GROUP (USA) INC."
        )
        self.assertEqual("exclude", quality.status)
        self.assertIn("title_page", quality.reasons)

    def test_excludes_copyright_page(self) -> None:
        quality = assess_chunk_quality(
            "Copyright 2026 Example Publisher. All rights reserved. ISBN 1234567890."
        )
        self.assertEqual("exclude", quality.status)
        self.assertIn("copyright_page", quality.reasons)

    def test_excludes_reference_list_continuation(self) -> None:
        quality = assess_chunk_quality(
            "\n".join(
                [
                    "10 Example, A History of Tarot, page 12.",
                    "11 Ibid., page 14.",
                    "12 Scholar, Symbols and Cards, New York Press: 1989.",
                    "13 Ibid., page 20.",
                    "14 Archive Library, vol. 2, 2005.",
                ]
            )
        )
        self.assertEqual("exclude", quality.status)
        self.assertIn("reference_list", quality.reasons)

    def test_excludes_pure_card_list(self) -> None:
        quality = assess_chunk_quality(
            "\n".join(
                [
                    "The Fool",
                    "The Magician",
                    "The High Priestess",
                    "The Empress",
                    "The Emperor",
                    "The Hierophant",
                    "The Lovers",
                    "The Chariot",
                    "Strength",
                    "The Hermit",
                ]
            )
        )
        self.assertEqual("exclude", quality.status)
        self.assertIn("pure_list", quality.reasons)

    def test_keeps_list_with_explanation(self) -> None:
        quality = assess_chunk_quality(
            "\n".join(
                [
                    "The Fool",
                    "The Magician",
                    "The High Priestess",
                    "The Empress",
                    "The Emperor",
                    "The Hierophant",
                    "The Lovers",
                    "The Chariot",
                    "These cards represent a symbolic journey. Each image has a distinct meaning.",
                    "The sequence explains how the major arcana can be read as a narrative.",
                ]
            )
        )
        self.assertNotEqual("exclude", quality.status)

    def test_keeps_narrative_that_mentions_published_by(self) -> None:
        quality = assess_chunk_quality(
            "The first interpretation was published by a French occultist. "
            "After that date, scholars began to treat the Tarot as a book of symbols. "
            "This historical shift changed later reading practices and influenced modern decks."
        )
        self.assertNotEqual("exclude", quality.status)

    def test_keeps_short_multiline_explanation(self) -> None:
        quality = assess_chunk_quality(
            "削弱法\n"
            "有些人会把逆位理解为影响力减弱；在这种方法中，正位牌仍然是解释重点。\n"
            "逆位牌用于补充说明，而不是完全失去含义。占卜者需要结合问题与周围牌面进行判断和复盘。"
        )
        self.assertNotEqual("exclude", quality.status)

    def test_merges_short_tail_chunk(self) -> None:
        chunks = split_page_into_chunks(
            "sample.pdf",
            1,
            f"{'A' * 900} {'B' * 900} short tail",
            max_chars=900,
        )
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk.text) >= 80 for chunk in chunks))
        self.assertTrue(chunks[-1].text.endswith("short tail"))

    def test_page_override_can_force_keep_downrank_and_exclude(self) -> None:
        overrides = {
            ("sample.pdf", 4): "force_keep",
            ("sample.pdf", 5): "force_exclude",
            ("sample.pdf", 6): "force_downrank",
        }
        kept = assess_chunk_quality("Table of Contents\nChapter 1\nChapter 2", "sample.pdf", 4, overrides)
        excluded = assess_chunk_quality("Useful explanation " * 20, "sample.pdf", 5, overrides)
        downranked = assess_chunk_quality("Useful explanation " * 20, "sample.pdf", 6, overrides)
        self.assertEqual("keep", kept.status)
        self.assertIn("override:force_keep", kept.reasons)
        self.assertEqual("exclude", excluded.status)
        self.assertIn("override:force_exclude", excluded.reasons)
        self.assertEqual("downrank", downranked.status)
        self.assertIn("override:force_downrank", downranked.reasons)

    def test_override_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = SimpleNamespace(data_dir=Path(temp_dir))
            set_filter_override(config, "book.pdf", 7, "force_exclude")
            set_filter_override(config, "book.pdf", 8, "force_downrank")
            self.assertEqual(
                {("book.pdf", 7): "force_exclude", ("book.pdf", 8): "force_downrank"},
                load_filter_overrides(config),
            )
            self.assertEqual(
                [
                    {"source_file": "book.pdf", "page": 7, "action": "force_exclude"},
                    {"source_file": "book.pdf", "page": 8, "action": "force_downrank"},
                ],
                list_filter_overrides(config),
            )
            set_filter_override(config, "book.pdf", 7, "clear")
            set_filter_override(config, "book.pdf", 8, "clear")
            self.assertEqual({}, load_filter_overrides(config))


if __name__ == "__main__":
    unittest.main()
