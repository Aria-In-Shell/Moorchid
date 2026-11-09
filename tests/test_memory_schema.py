"""Unit tests for layered memory schema and write rules."""

from __future__ import annotations

import unittest

from memory_schema import (
    assemble_prompt_memory,
    canonicalize_emotion,
    make_memory,
    memories_from_pattern,
    suggest_long_term,
    valence_for_emotion,
    PatternExtraction,
)


class MemorySchemaTests(unittest.TestCase):
    def test_canonicalize_emotion(self) -> None:
        self.assertEqual(canonicalize_emotion("开心"), "Joy")
        self.assertEqual(canonicalize_emotion("anxious"), "Anxious")
        self.assertEqual(canonicalize_emotion("Joy"), "Joy")

    def test_valence_high_and_low(self) -> None:
        self.assertGreater(valence_for_emotion("Joy"), 0.5)
        self.assertLess(valence_for_emotion("Anxious"), -0.5)

    def test_user_statement_cannot_come_from_agent(self) -> None:
        with self.assertRaises(ValueError):
            make_memory(
                user_id="ada",
                layer="event",
                content="hello",
                source="pattern_agent",
                statement_kind="user_statement",
                confidence=1.0,
            )

    def test_pattern_split_user_and_inference(self) -> None:
        extraction = PatternExtraction(
            emotion="Low",
            display_emotion="疲惫",
            valence=-0.5,
            intensity=0.6,
            tags=["#加班"],
            themes=["工作"],
            events=[{"summary": "加班到很晚", "confidence": 0.8}],
            inferences=[{"claim": "可能在透支精力", "confidence": 0.55}],
        )
        records = memories_from_pattern(
            user_id="ada",
            entry_id=1,
            content="今天加班到很晚，有点撑不住。",
            extraction=extraction,
        )
        kinds = {r["provenance"]["statement_kind"] for r in records}
        self.assertIn("user_statement", kinds)
        self.assertIn("model_inference", kinds)
        user = next(r for r in records if r["provenance"]["statement_kind"] == "user_statement")
        self.assertEqual(user["provenance"]["source"], "user")
        self.assertEqual(user["provenance"]["confidence"], 1.0)

    def test_long_term_requires_recurrence(self) -> None:
        extraction = PatternExtraction(
            emotion="Anxious",
            display_emotion="焦虑",
            valence=-0.8,
            intensity=0.7,
            tags=["#论文"],
            themes=["学业"],
            events=[],
            inferences=[],
        )
        events = []
        for i in range(3):
            events.extend(
                memories_from_pattern(
                    user_id="ada",
                    entry_id=i + 1,
                    content=f"论文进度 {i}",
                    extraction=extraction,
                )
            )
        promoted = suggest_long_term(events)
        self.assertTrue(any(r["layer"] == "long_term" for r in promoted))
        self.assertTrue(any("学业" in (r.get("themes") or []) for r in promoted))

    def test_prompt_separates_kinds(self) -> None:
        extraction = PatternExtraction(
            emotion="Calm",
            display_emotion="平静",
            valence=0.4,
            intensity=0.4,
            tags=["#散步"],
            themes=["日常"],
            events=[{"summary": "晚间散步", "confidence": 0.9}],
            inferences=[],
        )
        events = memories_from_pattern(
            user_id="ada",
            entry_id=9,
            content="傍晚去河边走了一圈。",
            extraction=extraction,
        )
        prompt = assemble_prompt_memory(events=events)
        self.assertIn("用户陈述", prompt)
        self.assertIn("模型推断", prompt)


if __name__ == "__main__":
    unittest.main()
