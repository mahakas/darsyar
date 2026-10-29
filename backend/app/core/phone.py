"""نرمال‌سازی شمارهٔ تلفن به E.164 (R-099)."""

import re

IRAN_MOBILE_RE = re.compile(r"^\+989\d{9}$")

PHONE_NORMALIZATION_ERROR = "invalid_phone"


def normalize_e164(raw: str) -> str:
    """شمارهٔ ایرانی را به E.164 نرمال می‌کند؛ ورودی‌های 09…/0098…/+98… یکسان می‌شوند."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("98") and len(digits) == 12:
        digits = digits
    elif digits.startswith("0") and len(digits) == 11:
        digits = "98" + digits[1:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "98" + digits
    normalized = "+" + digits
    if not IRAN_MOBILE_RE.fullmatch(normalized):
        raise ValueError(PHONE_NORMALIZATION_ERROR)
    return normalized
