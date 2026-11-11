"""Common PDF Validation Layer (Gate B-S0, synthetic-only).

Reusable, explicitly invoked validation component for PDF ingestion. It performs
byte-level identity checks and structural validation **without** extracting text or
rendering pages. It is not wired to any application route in this stage.

Security posture:
- Never trusts filename or MIME; validates actual bytes.
- Rejects empty input and enforces a caller-supplied maximum file-byte policy.
- Uses pypdf (parser only; not the approved renderer) for structural parsing,
  page counting, and encryption detection.
- Maps parser exceptions to safe, typed domain outcomes — raw parser exceptions are
  never exposed to callers.
- Encrypted documents are detected and rejected as policy-required; no password
  handling is provided or performed.
- IMPORTANT limitation (recorded): pypdf does not expose a comprehensive
  decompressed-object / stream-size enforcement mechanism. This component does NOT
  claim full decompression-bomb protection. Only safeguards that can be reliably
  enforced are added; missing protections remain Gate B blockers.

Policy contract: all numeric thresholds are explicit, caller-supplied inputs. No
production defaults, no hidden values, no config fields are introduced here.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pypdf
from pypdf.errors import (
    EmptyFileError,
    PdfReadError,
    PdfStreamError,
    PyPdfError,
    WrongPasswordError,
)

from app.core.logging import get_logger

logger = get_logger(__name__)

PDF_SIGNATURE = b"%PDF-"


class PdfValidationStatus(str, Enum):
    """Structured validation outcome categories (safe to expose)."""

    VALID = "valid"
    EMPTY = "empty"
    INVALID_SIGNATURE = "invalid_signature"
    MALFORMED = "malformed"
    TRUNCATED = "truncated"
    ENCRYPTED = "encrypted"
    EXCEEDS_FILE_BYTES = "exceeds_file_bytes"
    EXCEEDS_PAGES = "exceeds_pages"
    PARSER_UNAVAILABLE = "parser_unavailable"


@dataclass(frozen=True)
class PdfValidationPolicy:
    """Explicit validation policy input.

    No defaults: numeric thresholds are mandatory, caller-supplied values.
    Tests may supply small explicit synthetic thresholds. The active application
    must not instantiate this as an operational upload policy yet.
    """

    max_file_bytes: int
    max_pages: int


@dataclass(frozen=True)
class PdfValidationResult:
    """Typed, sanitized validation outcome."""

    status: PdfValidationStatus
    page_count: int | None = None
    is_encrypted: bool = False
    error_detail: str | None = None
    # Reserved for future parent/child contract correlation (not populated in S0).
    _reserved: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


def validate_pdf(data: bytes, policy: PdfValidationPolicy) -> PdfValidationResult:
    """Validate PDF bytes against an explicit policy.

    Returns a structured :class:`PdfValidationResult`. Never raises raw parser
    exceptions to callers; does not extract text or render pages.
    """
    if not data:
        return PdfValidationResult(status=PdfValidationStatus.EMPTY)
    if len(data) > policy.max_file_bytes:
        return PdfValidationResult(
            status=PdfValidationStatus.EXCEEDS_FILE_BYTES,
            error_detail=f"size={len(data)} policy_max={policy.max_file_bytes}",
        )
    if not data.startswith(PDF_SIGNATURE):
        return PdfValidationResult(status=PdfValidationStatus.INVALID_SIGNATURE)

    try:
        reader = pypdf.PdfReader(io.BytesIO(data), strict=False)
    except PdfStreamError:
        # Truncated/stream-corrupted document (PdfStreamError < PdfReadError).
        return PdfValidationResult(status=PdfValidationStatus.TRUNCATED)
    except (WrongPasswordError, PdfReadError) as exc:
        # Password-protected / encrypted: detect and reject; never attempt decrypt.
        if _looks_encrypted(exc):
            return PdfValidationResult(status=PdfValidationStatus.ENCRYPTED, is_encrypted=True)
        return PdfValidationResult(status=PdfValidationStatus.MALFORMED, error_detail=_safe_code(exc))
    except EmptyFileError:
        return PdfValidationResult(status=PdfValidationStatus.EMPTY)
    except PyPdfError as exc:
        return PdfValidationResult(status=PdfValidationStatus.MALFORMED, error_detail=_safe_code(exc))
    except Exception as exc:  # noqa: BLE001 - map unknown parser failures to safe domain error
        logger.warning("pdf_validation_parser_unexpected", extra={"error_type": type(exc).__name__})
        return PdfValidationResult(status=PdfValidationStatus.MALFORMED, error_detail="parser_failure")

    if reader.is_encrypted:
        return PdfValidationResult(status=PdfValidationStatus.ENCRYPTED, is_encrypted=True)

    try:
        page_count = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf_validation_pagecount_failure", extra={"error_type": type(exc).__name__})
        return PdfValidationResult(status=PdfValidationStatus.MALFORMED, error_detail="pagecount_failure")

    if page_count > policy.max_pages:
        return PdfValidationResult(
            status=PdfValidationStatus.EXCEEDS_PAGES,
            page_count=page_count,
            error_detail=f"pages={page_count} policy_max={policy.max_pages}",
        )

    return PdfValidationResult(status=PdfValidationStatus.VALID, page_count=page_count)


def _safe_code(exc: Exception) -> str:
    """Return a stable, non-sensitive error code derived from the exception type."""
    return type(exc).__name__


def _looks_encrypted(exc: Exception) -> bool:
    """Best-effort heuristic for encryption signals from parser errors."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "password" in name or "encrypt" in name or "password" in message or "encrypt" in message
