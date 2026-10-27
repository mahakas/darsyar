"""قرارداد مدل inference؛ بارگذاری واقعی مدل در فاز ۳ انجام می‌شود."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InferenceStatus:
    """وضعیت بی‌حاشیهٔ بارگذاری inference را نمایش می‌دهد."""
    ready: bool
    mode: str
    embedding_model: str
    embedding_dim: int
    reranker_model: str
    device: str
    message: str
