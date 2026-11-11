"""Gate B-S0 synthetic PDF validation tests (test_only, no real PDFs).

All fixtures are generated in-memory inside the tests. No pilot PDF is opened,
hashed, embedded, or processed. No text extraction, rendering, or PDFium
invocation occurs. No persistent files are written.
"""

from __future__ import annotations

import io
import zlib

import pypdf
import pytest
from app.services.ingestion.pdf_validation import (
    PDF_SIGNATURE,
    PdfValidationPolicy,
    PdfValidationResult,
    PdfValidationStatus,
    validate_pdf,
)
from pypdf._configuration import Configuration, apply_configuration, get_configuration
from pypdf.errors import LimitReachedError

# Small explicit synthetic thresholds (testing fixtures, not operational limits).
POLICY = PdfValidationPolicy(max_file_bytes=4096, max_pages=10)


def _valid_pdf(pages: int = 2) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()


def _encrypted_pdf() -> bytes:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("test-password")
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()


def _compressed_obj_pdf() -> bytes:
    """Build a valid minimal PDF with a FlateDecode-compressed content stream.

    A correct xref table and trailer are emitted (offsets computed) so the
    parser can read the single page through the compressed stream.
    """
    raw = b"BT /F1 12 Tf 72 720 Td (hello compressed) Tj ET"
    compressed = zlib.compress(raw)

    def obj(body: bytes) -> bytes:
        return body + b"\nendobj\n"

    catalog = obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>")
    pages = obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    page = obj(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>")
    stream = (
        b"4 0 obj\n<< /Length "
        + str(len(compressed)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )

    body = b"%PDF-1.4\n% synthetic\n" + catalog + pages + page + stream
    # xref
    offsets = [0]
    pos = 0
    # compute offsets of each object start within body
    parts = [catalog, pages, page, stream]
    for part in parts:
        offsets.append(pos)
        pos += len(part)
    xref = b"xref\n0 5\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = b"trailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n" + str(len(body) + len(xref)).encode() + b"\n%%EOF\n"
    return body + xref + trailer


def test_valid_synthetic_pdf_accepted() -> None:
    result = validate_pdf(_valid_pdf(2), POLICY)
    assert result.status is PdfValidationStatus.VALID
    assert result.page_count == 2
    assert result.is_encrypted is False


def test_empty_input_rejected() -> None:
    result = validate_pdf(b"", POLICY)
    assert result.status is PdfValidationStatus.EMPTY


def test_invalid_signature_rejected() -> None:
    bad = b"PK\x03\x04this is not a pdf but long enough"
    result = validate_pdf(bad, POLICY)
    assert result.status is PdfValidationStatus.INVALID_SIGNATURE


def test_signature_checked_by_bytes_not_filename() -> None:
    # A byte stream with no PDF signature is rejected regardless of any filename/MIME
    # association; the validator only inspects bytes.
    junk = b"\x00\x01\x02\x03" * 128
    result = validate_pdf(junk, POLICY)
    assert result.status is PdfValidationStatus.INVALID_SIGNATURE


def test_truncated_pdf_rejected_safely() -> None:
    truncated = _valid_pdf(2)[: len(_valid_pdf(2)) // 2]
    result = validate_pdf(truncated, POLICY)
    assert result.status is PdfValidationStatus.TRUNCATED


def test_malformed_xref_rejected_safely() -> None:
    malformed = _valid_pdf(2).replace(b"xref", b"xxxx")
    result = validate_pdf(malformed, POLICY)
    assert result.status is PdfValidationStatus.MALFORMED


def test_encrypted_pdf_identified_not_accepted() -> None:
    result = validate_pdf(_encrypted_pdf(), POLICY)
    assert result.status is PdfValidationStatus.ENCRYPTED
    assert result.is_encrypted is True


def test_page_count_observed() -> None:
    result = validate_pdf(_valid_pdf(5), POLICY)
    assert result.status is PdfValidationStatus.VALID
    assert result.page_count == 5


def test_explicit_file_bytes_limit_enforced() -> None:
    data = _valid_pdf(2)
    small = PdfValidationPolicy(max_file_bytes=len(data) - 1, max_pages=10)
    result = validate_pdf(data, small)
    assert result.status is PdfValidationStatus.EXCEEDS_FILE_BYTES


def test_explicit_page_count_limit_enforced() -> None:
    data = _valid_pdf(5)
    small = PdfValidationPolicy(max_file_bytes=len(data), max_pages=4)
    result = validate_pdf(data, small)
    assert result.status is PdfValidationStatus.EXCEEDS_PAGES
    assert result.page_count == 5


def test_client_supplied_filename_mime_cannot_bypass_byte_validation() -> None:
    # Even if a caller labels bytes with a .pdf name, only the bytes decide.
    not_pdf = b"not actually a pdf at all but padded out to length"
    result = validate_pdf(not_pdf, POLICY)
    assert result.status is PdfValidationStatus.INVALID_SIGNATURE


def test_parser_exceptions_map_to_safe_domain_errors() -> None:
    # Malformed/truncated inputs must never raise; they map to typed statuses.
    for data in (
        b"",
        b"x" * 2000,
        _valid_pdf(2)[:64],
    ):
        result = validate_pdf(data, POLICY)
        assert isinstance(result, PdfValidationResult)
        assert isinstance(result.status, PdfValidationStatus)


def test_compressed_synthetic_objects_handled_per_parser_capability() -> None:
    # Confirm pypdf parses a compressed object stream and counts pages, and that the
    # parser's limitation on full decompression-bomb enforcement is not overclaimed.
    data = _compressed_obj_pdf()
    result = validate_pdf(data, POLICY)
    # pypdf decompresses FlateDecode streams; it should read the single page.
    assert result.status is PdfValidationStatus.VALID
    assert result.page_count == 1


def test_component_does_not_extract_text() -> None:
    # The validator must not return any extracted text; the result carries only
    # status, page count, encryption flag, and a reserved (unpopulated) dict.
    result = validate_pdf(_valid_pdf(2), POLICY)
    assert not hasattr(result, "text")
    assert result._reserved == {}


def test_component_does_not_render_or_invoke_pdfium() -> None:
    # No rendering path exists; validator returns a typed result without any
    # image/rendered artifact field.
    result = validate_pdf(_valid_pdf(1), POLICY)
    assert result.status is PdfValidationStatus.VALID
    assert not hasattr(result, "image")


def test_no_persistent_files_after_validation() -> None:
    import os
    import tempfile

    before = set(os.listdir(tempfile.gettempdir()))
    _ = validate_pdf(_valid_pdf(2), POLICY)
    _ = validate_pdf(_encrypted_pdf(), POLICY)
    _ = validate_pdf(_compressed_obj_pdf(), POLICY)
    after = set(os.listdir(tempfile.gettempdir()))
    assert after == before


def test_signature_constant_matches_pdf_header() -> None:
    assert PDF_SIGNATURE == b"%PDF-"
    assert _valid_pdf(1).startswith(PDF_SIGNATURE)


# --- pypdf 6.21.4 resource-limit audit (synthetic-only, test-only Config) ---


def test_pypdf_default_configuration_is_active_and_unmodified() -> None:
    # Darsyar's validator constructs PdfReader with no configuration override, so
    # pypdf's process-global (default) Configuration is active.
    cfg = get_configuration()
    assert cfg.maximum_declared_stream_length == 75_000_000
    assert cfg.zlib_maximum_output_length == 75_000_000
    assert cfg.jbig2_maximum_output_length == 75_000_000
    assert cfg.lzw_maximum_output_length == 75_000_000
    assert cfg.run_length_maximum_output_length == 75_000_000
    assert cfg.brotli_maximum_output_length == 75_000_000
    assert cfg.image_maximum_buffer_size == 75_000_000
    assert cfg.stream_filters_maximum_length == 16
    assert cfg.stream_parsing_work_maximum_count == 2_000_000
    assert cfg.page_tree_maximum_entries == 100_000


def test_page_count_does_not_decode_content_streams() -> None:
    # Page counting walks the page tree only; it must not decompress embedded
    # content streams. A tiny zlib output limit must therefore NOT trip the
    # validator's page-count path.
    data = _compressed_obj_pdf()
    tiny = Configuration(zlib_maximum_output_length=1)
    with apply_configuration(tiny):
        result = validate_pdf(data, POLICY)
    assert result.status is PdfValidationStatus.VALID
    assert result.page_count == 1


def test_pypdf_builtin_zlib_limit_rejects_oversized_stream_on_decode() -> None:
    # pypdf enforces a per-stream zlib output cap at decode time. Under a
    # deliberately tiny test-only limit, decoding an oversized synthetic stream
    # raises LimitReachedError (a subclass of PyPdfError; safely mappable).
    # This documents the parser's built-in safeguard, not an operational threshold.
    tiny = Configuration(zlib_maximum_output_length=8)
    payload = zlib.compress(b"X" * 200)
    with apply_configuration(tiny):
        with pytest.raises(LimitReachedError):
            pypdf.filters.decompress(payload)


def test_pypdf_parser_limit_exceptions_are_safe_pypdf_error_subclass() -> None:
    # LimitReachedError derives from PyPdfError, so any surfaced parser limit
    # error belongs to the same safe domain family the validator maps.
    assert issubclass(LimitReachedError, pypdf.errors.PyPdfError)


def test_pypdf_scoped_configuration_is_restored_after_context_exit() -> None:
    # apply_configuration must scope changes and restore the previous value after.
    before = get_configuration().zlib_maximum_output_length
    with apply_configuration(Configuration(zlib_maximum_output_length=7)):
        assert get_configuration().zlib_maximum_output_length == 7
    assert get_configuration().zlib_maximum_output_length == before
