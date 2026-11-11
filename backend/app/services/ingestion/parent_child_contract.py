"""Parent/Child ingestion processing contract — versioned IPC types (Gate B-S1).

Defines the versioned serialization contract for the Parent Supervisor → Isolated
PDF Child prototype. In S1 this contract is used by real OS-process IPC
(stdin/stdout JSON). Security invariants remain:

- The child must never receive database URLs, database/Redis credentials,
  application secrets, session objects, or infrastructure clients.
- The parent owns all database/application-infrastructure access and all
  consequential commits.
- Only minimal synthetic document bytes and explicit test-supplied limits cross
  the wire.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

PARENT_CHILD_CONTRACT_VERSION = 1


class ChildProcessingOutcome(str, Enum):
    """Typed processing outcome returned by the child."""

    SUCCESS = "success"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class ChildErrorCategory(str, Enum):
    """Structured error category (safe to expose; no raw parser surfaces)."""

    NONE = "none"
    MALFORMED = "malformed"
    TRUNCATED = "truncated"
    ENCRYPTED = "encrypted"
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"
    INTERNAL = "internal"


@dataclass(frozen=True)
class ParentChildRequest:
    """Request contract: parent → child (over stdin as JSON).

    Carries only synthetic document bytes (base64) and explicit, test-supplied
    limits. No credentials, secrets, session objects, or client handles.
    """

    contract_version: int = PARENT_CHILD_CONTRACT_VERSION
    attempt_id: str = ""
    document_bytes: bytes = b""
    # Explicit test-supplied limits. No production defaults are invented.
    limits: dict[str, Any] = field(default_factory=dict)
    # Child mode for synthetic scenarios; "normal" unless a test overrides.
    mode: str = "normal"

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "contract_version": self.contract_version,
            "attempt_id": self.attempt_id,
            "document_bytes": base64.b64encode(self.document_bytes).decode("ascii"),
            "limits": self.limits,
            "mode": self.mode,
        }
        return json.dumps(payload)

    @classmethod
    def from_json(cls, raw: str) -> ParentChildRequest:
        payload = json.loads(raw)
        return cls(
            contract_version=int(payload.get("contract_version", PARENT_CHILD_CONTRACT_VERSION)),
            attempt_id=str(payload.get("attempt_id", "")),
            document_bytes=base64.b64decode(payload.get("document_bytes", "")),
            limits=dict(payload.get("limits", {})),
            mode=str(payload.get("mode", "normal")),
        )


@dataclass(frozen=True)
class ParentChildResult:
    """Result contract: child → parent (over stdout as JSON).

    Identifies contract version, attempt/correlation ID, processing outcome, a
    structured error category, page count, optional decoded-stream length, the
    child's pypdf version, and optionally recorded memory. No credentials or
    secrets are part of this result.
    """

    contract_version: int = PARENT_CHILD_CONTRACT_VERSION
    attempt_id: str = ""
    outcome: ChildProcessingOutcome = ChildProcessingOutcome.UNSUPPORTED
    error_category: ChildErrorCategory = ChildErrorCategory.NONE
    page_count: int | None = None
    decoded_stream_length: int | None = None
    pypdf_version: str = ""
    memory_bytes: int | None = None
    artifact_metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "contract_version": self.contract_version,
            "attempt_id": self.attempt_id,
            "outcome": self.outcome.value,
            "error_category": self.error_category.value,
            "page_count": self.page_count,
            "decoded_stream_length": self.decoded_stream_length,
            "pypdf_version": self.pypdf_version,
            "memory_bytes": self.memory_bytes,
            "artifact_metadata": self.artifact_metadata,
        }
        return json.dumps(payload)

    @classmethod
    def from_json(cls, raw: str) -> ParentChildResult:
        payload = json.loads(raw)
        return cls(
            contract_version=int(payload.get("contract_version", PARENT_CHILD_CONTRACT_VERSION)),
            attempt_id=str(payload.get("attempt_id", "")),
            outcome=ChildProcessingOutcome(payload.get("outcome", ChildProcessingOutcome.UNSUPPORTED.value)),
            error_category=ChildErrorCategory(payload.get("error_category", ChildErrorCategory.NONE.value)),
            page_count=payload.get("page_count"),
            decoded_stream_length=payload.get("decoded_stream_length"),
            pypdf_version=str(payload.get("pypdf_version", "")),
            memory_bytes=payload.get("memory_bytes"),
            artifact_metadata=dict(payload.get("artifact_metadata", {})),
        )
