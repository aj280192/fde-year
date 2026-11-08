"""Retrieval metrics: pure functions, no database and no model.

They work on any hashable item (a Hit, a tuple, a string), so the tests don't
need to import retrieve.py, which would load PyTorch.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence


def recall_at_k[T: Hashable](retrieved: Sequence[T], relevant: set[T], k: int) -> float:
    """Share of the relevant items found in the top k."""
    if not relevant:
        raise ValueError("relevant is empty: recall is undefined")
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def mrr_at_k[T: Hashable](retrieved: Sequence[T], relevant: set[T], k: int) -> float:
    """1 / rank of the first relevant item in the top k; 0 if none."""
    for rank, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
