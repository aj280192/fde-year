"""The abstain rules, as pure functions: no model, no database.

rag.py calls them before and after generation; test_checks.py tests them directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config import ABSTAIN_TEXT

# A citation such as [B6:154], or [B6:154#2] for a second piece of one paragraph.
CITATION = re.compile(r"\[(B\d+:\d+(?:#\d+)?)\]")

# Reasoning models (Qwen 3, DeepSeek R1) may put their working in <think>…</think> before the answer.
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass(frozen=True)
class Source:
    id: str  # "B6:154", or "B6:154#2"
    booklet: int
    paragraph: int  # the content paragraph: the last entry in the chunk's covers
    text: str
    score: float  # the cross-encoder score


def check_retrieval(sources: list[Source], threshold: float) -> str | None:
    """A reason to abstain before calling the model, or None."""
    if not sources:
        return "no_sources"
    if sources[0].score < threshold:
        return "low_retrieval_score"
    return None


def check_answer(text: str, allowed_ids: set[str]) -> tuple[str | None, list[str]]:
    """(a reason to abstain, or None; the cited ids, unique, in order of first mention)."""
    if text.strip().lower().startswith(ABSTAIN_TEXT):
        return "model_abstained", []
    cited = list(dict.fromkeys(CITATION.findall(text)))
    if not cited:
        return "no_citations", []
    if any(c not in allowed_ids for c in cited):
        return "unknown_citation", cited
    return None, cited


def strip_thinking(text: str) -> str:
    """The answer without any <think>…</think> block, so only the final answer is checked and shown."""
    return THINKING.sub("", text).strip()
