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
import binascii
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

PARENT_CHILD_CONTRACT_VERSION = 1

REQUEST_KEYS = {"contract_version", "attempt_id", "document_bytes", "limits", "mode"}
RESULT_KEYS = {
    "contract_version",
    "attempt_id",
    "outcome",
    "error_category",
    "page_count",
    "decoded_stream_length",
    "pypdf_version",
    "memory_bytes",
    "artifact_metadata",
}
REQUEST_LIMIT_KEYS = {"zlib_maximum_output_length"}


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _load_json_object(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise ValueError("JSON payload must be text")
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("invalid JSON constant")),
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _require_exact_keys(payload: dict[str, Any], expected: set[str]) -> None:
    if payload.keys() != expected:
        raise ValueError("JSON payload fields do not match the contract")


def _require_int(value: Any, field_name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")
    return value


def _require_optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, field_name)


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
    INVALID_REQUEST = "invalid_request"


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
        payload = _load_json_object(raw)
        _require_exact_keys(payload, REQUEST_KEYS)

        version = _require_int(payload["contract_version"], "contract_version", minimum=1)
        attempt_id = payload["attempt_id"]
        encoded_bytes = payload["document_bytes"]
        limits = payload["limits"]
        mode = payload["mode"]

        if not isinstance(attempt_id, str) or not attempt_id.strip():
            raise ValueError("attempt_id must be a non-empty string")
        if not isinstance(encoded_bytes, str):
            raise ValueError("document_bytes must be a base64 string")
        try:
            document_bytes = base64.b64decode(encoded_bytes, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("document_bytes is not valid base64") from exc
        if not isinstance(limits, dict) or not limits.keys() <= REQUEST_LIMIT_KEYS:
            raise ValueError("limits must be an object with only supported keys")
        # Validate the wire shape here, but leave policy-value validation to the
        # child processor so it can return a typed INVALID_REQUEST result.
        if not isinstance(mode, str) or not mode:
            raise ValueError("mode must be a non-empty string")

        return cls(
            contract_version=version,
            attempt_id=attempt_id,
            document_bytes=document_bytes,
            limits=limits,
            mode=mode,
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
        payload = _load_json_object(raw)
        _require_exact_keys(payload, RESULT_KEYS)

        version = _require_int(payload["contract_version"], "contract_version", minimum=1)
        attempt_id = payload["attempt_id"]
        pypdf_version = payload["pypdf_version"]
        artifact_metadata = payload["artifact_metadata"]
        if not isinstance(attempt_id, str) or not attempt_id.strip():
            raise ValueError("attempt_id must be a non-empty string")
        if not isinstance(pypdf_version, str):
            raise ValueError("pypdf_version must be a string")
        if not isinstance(artifact_metadata, dict) or any(not isinstance(key, str) for key in artifact_metadata):
            raise ValueError("artifact_metadata must be an object with string keys")

        return cls(
            contract_version=version,
            attempt_id=attempt_id,
            outcome=ChildProcessingOutcome(payload["outcome"]),
            error_category=ChildErrorCategory(payload["error_category"]),
            page_count=_require_optional_int(payload["page_count"], "page_count"),
            decoded_stream_length=_require_optional_int(payload["decoded_stream_length"], "decoded_stream_length"),
            pypdf_version=pypdf_version,
            memory_bytes=_require_optional_int(payload["memory_bytes"], "memory_bytes"),
            artifact_metadata=artifact_metadata,
        )
