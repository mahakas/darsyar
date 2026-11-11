"""Phase 4: manifest validation (R-153/R-154/R-157).

Validates a `manifest.yaml` for a source document before ingestion. Strict,
fail-closed rules: missing/invalid grade mapping, subject, or identity → error
or `needs_review`; no guessing (R-152). The manifest metadata is the provenance
identity source; it does NOT itself grant licensing (ADR-024).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.errors import AppError

SUPPORTED_SUBJECTS = {
    "math", "science", "physics", "chemistry", "biology", "persian", "arabic",
    "english", "quran", "social_studies", "religious_studies", "vocation", "defense",
}

# Required manifest fields (R-154), with types.
REQUIRED_FIELDS: dict[str, type] = {
    "path": str,
    "subject": str,
    "grade": int,
    "edition_year": int,
    "title": str,
    "publisher": str,
    "license_note": str,
}


@dataclass(frozen=True)
class Manifest:
    path: str
    subject: str
    grade: int
    edition_year: int
    title: str
    publisher: str
    license_note: str
    checksum: str | None = None
    raw: dict[str, Any] | None = None


def load_manifest(path: Path | str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        raise AppError("manifest_unreadable", 422, "manifest قابل خواندن نیست.") from exc
    except yaml.YAMLError as exc:
        raise AppError("manifest_malformed", 422, "manifest ساختار YAML نامعتبر دارد.") from exc
    if not isinstance(data, dict):
        raise AppError("manifest_malformed", 422, "manifest باید نگاشت ریشه داشته باشد.")
    return data


def validate_manifest(path: Path | str, *, manifest: dict[str, Any] | None = None) -> Manifest:
    """Validate a manifest; raise a typed AppError on any invalid field."""
    if manifest is None:
        manifest = load_manifest(path)

    for field, expected_type in REQUIRED_FIELDS.items():
        value = manifest.get(field)
        if value is None:
            raise AppError("manifest_missing_field", 422, f"فیلد الزامی {field} ناقص است.")
        if not isinstance(value, expected_type):
            raise AppError("manifest_invalid_field", 422, f"فیلد {field} نوع نامعتبر دارد.")

    subject = manifest["subject"]
    if subject not in SUPPORTED_SUBJECTS:
        raise AppError("manifest_invalid_subject", 422, f"درس نامعتبر: {subject}")

    grade = int(manifest["grade"])
    if not 1 <= grade <= 12:
        raise AppError("manifest_invalid_grade", 422, "پایه باید بین ۱ و ۱۲ باشد.")

    edition_year = int(manifest["edition_year"])
    if edition_year <= 0:
        raise AppError("manifest_invalid_edition_year", 422, "سال چاپ نامعتبر است.")

    return Manifest(
        path=str(manifest["path"]),
        subject=subject,
        grade=grade,
        edition_year=edition_year,
        title=str(manifest["title"]),
        publisher=str(manifest["publisher"]),
        license_note=str(manifest["license_note"]),
        checksum=str(manifest["checksum"]) if manifest.get("checksum") else None,
        raw=manifest,
    )
