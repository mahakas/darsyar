"""pypdf version probe (Gate B-S4.2) — v2 (scans full package source)."""

from __future__ import annotations

import dataclasses
import json
import os
import platform
import sys
import zlib

import pypdf
import pypdf._reader as reader_mod
import pypdf.filters as filters_mod
from pypdf._configuration import Configuration
from pypdf.errors import LimitReachedError


def _package_text() -> str:
    root = os.path.dirname(os.path.dirname(pypdf.__file__))
    parts: list[str] = []
    for dirpath, _dirs, files in os.walk(os.path.join(root, "pypdf")):
        for fn in files:
            if fn.endswith(".py"):
                try:
                    with open(os.path.join(dirpath, fn), encoding="utf-8") as fh:
                        parts.append(fh.read())
                except OSError:
                    pass
    return "\n".join(parts)


def main() -> int:
    cfg = Configuration()
    fields = {f.name for f in dataclasses.fields(cfg)}
    text = _package_text()
    reader = ""
    try:
        reader = open(reader_mod.__file__, encoding="utf-8").read()  # noqa: SIM115
    except OSError:
        reader = ""

    # bounded zlib behavior
    zlib_raises = False
    try:
        with pypdf._configuration.apply_configuration(Configuration(zlib_maximum_output_length=8)):  # type: ignore[attr-defined]
            filters_mod.decompress(zlib.compress(b"X" * 200))
    except Exception as exc:  # noqa: BLE001
        zlib_raises = isinstance(exc, LimitReachedError)

    duplicate_lines = [ln.strip() for ln in reader.splitlines() if "duplicate" in ln.lower()][:8]

    summary = {
        "pypdf_version": pypdf.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_file": pypdf.__file__,
        "config_fields_present": sorted(
            fields
            & {
                "zlib_maximum_output_length",
                "lzw_maximum_output_length",
                "run_length_maximum_output_length",
                "jbig2_maximum_output_length",
                "brotli_maximum_output_length",
                "image_maximum_buffer_size",
                "stream_filters_maximum_length",
                "stream_decoding_work_maximum_length",
                "stream_parsing_work_maximum_count",
                "flate_maximum_columns",
                "flate_maximum_row_length",
                "array_based_stream_maximum_output_length",
                "maximum_declared_stream_length",
            }
        ),
        "xfa_limit_field_present": any("xfa" in f.lower() for f in fields),
        "marker_bytes_per_component": "bytes_per_component" in text,
        "marker_image_buffer_uses_bytesperpixel": "bytespercomponent" in text.lower() or "bytes_per_component" in text.lower(),
        "xref_duplicate_lines": duplicate_lines,
        "marker_xfa_present": "xfa" in text.lower() or "XFA" in text,
        "zlib_limit_reached_error_raised": zlib_raises,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
