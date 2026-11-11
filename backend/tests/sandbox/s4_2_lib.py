"""Gate B-S4.2 — test-only helpers.

Provides per-document child-process invocation (one isolated OS process per
document) by reusing the production `parent_supervisor.run_child` as a library
(no production module is modified), plus parse-time source-review introspection
helpers.
"""

from __future__ import annotations

import inspect
import os

import pypdf
from app.services.ingestion.parent_child_contract import ParentChildRequest
from app.services.ingestion.parent_supervisor import ChildRunResult, run_child

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_doc_child(
    document: bytes,
    *,
    timeout_seconds: float = 20,
    zlib_limit: int = 2000,
    mode: str = "normal",
) -> ChildRunResult:
    """Spawn one isolated child process for a synthetic document."""
    request = ParentChildRequest(
        contract_version=1,
        attempt_id="s42",
        document_bytes=document,
        limits={"zlib_maximum_output_length": zlib_limit},
        mode=mode,
    )
    return run_child(request, timeout_seconds=timeout_seconds, cwd=BACKEND_DIR)


def reader_init_calls() -> list[str]:
    """Which parse-time steps PdfReader.__init__ performs (source review)."""
    src = inspect.getsource(pypdf.PdfReader.__init__)
    calls: list[str] = []
    for line in src.splitlines():
        ls = line.strip()
        if ls.startswith(("self._", "self.")) and "(" in ls and "=" not in ls[:ls.index("(")]:
            calls.append(ls[:ls.index("(")] + "()")
    return calls


def parse_method_present(method: str) -> bool:
    return hasattr(pypdf.PdfReader, method)
