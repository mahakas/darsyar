"""Initial daily review policy. No persistence, inference or clock access."""

from datetime import date, timedelta
from enum import StrEnum


class Recall(StrEnum):
    AGAIN = "again"
    HARD = "hard"
    EASY = "easy"


POLICY_VERSION = 1
MAX_INTERVAL_DAYS = 90


def next_review(review_day: date, previous_days: int, recall: Recall) -> date:
    """Schedule from the actual local review day; zero denotes a new card."""
    if not 0 <= previous_days <= MAX_INTERVAL_DAYS:
        raise ValueError("previous_days outside review policy range")
    if recall == Recall.AGAIN:
        days = 1
    elif recall == Recall.HARD:
        days = max(2, previous_days // 2)
    elif recall == Recall.EASY:
        days = min(MAX_INTERVAL_DAYS, max(4, previous_days * 2))
    else:
        raise ValueError("unknown recall rating")
    return review_day + timedelta(days=days)
