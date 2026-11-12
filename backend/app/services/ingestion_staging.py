"""Synthetic, attempt-scoped artifact staging and fenced publication.

This module deliberately uses only a caller-supplied local directory. It does not
configure upload paths, process PDFs, start workers, or choose retention limits.
The parent owns the PostgreSQL session and all publication decisions.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_job import IngestionJob
from app.services.ingestion_jobs import IngestionJobLease

_ARTIFACT_NAME_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_MEDIA_TYPE_RE: Final[re.Pattern[str]] = re.compile(
    r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+\Z"
)
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}\Z")
_COPY_CHUNK_SIZE: Final[int] = 1024 * 1024


class StagingArtifactError(ValueError):
    """Artifact metadata, integrity, path, or size validation failed."""


class StaleArtifactAttemptError(RuntimeError):
    """The artifact attempt no longer owns a live, uncancelled job lease."""


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    """Safe, content-addressed metadata for one immutable attempt artifact."""

    job_id: uuid.UUID
    fencing_token: int
    artifact_name: str
    relative_path: str
    byte_length: int
    sha256: str
    media_type: str


def _validate_positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StagingArtifactError(f"{name} must be a positive integer")


def _validate_artifact_name(value: str) -> None:
    if not isinstance(value, str) or _ARTIFACT_NAME_RE.fullmatch(value) is None:
        raise StagingArtifactError("artifact_name must be a safe ASCII file name")


def _validate_media_type(value: str) -> None:
    if not isinstance(value, str) or _MEDIA_TYPE_RE.fullmatch(value) is None:
        raise StagingArtifactError("media_type must be a lowercase type/subtype value")


def _validate_now(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise StagingArtifactError("now must be timezone-aware")


class StagingArtifactStore:
    """Explicit-root staging store for synthetic parent-owned artifacts.

    All size limits are explicit method arguments; no runtime defaults are
    selected. Staging and published paths include both job UUID and fencing token,
    so attempts cannot overwrite one another. Publication is an atomic hard-link
    inside the same filesystem and is authorized by a locked PostgreSQL job row.
    """

    def __init__(self, root: Path) -> None:
        raw_root = Path(root)
        raw_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if raw_root.is_symlink() or not raw_root.is_dir():
            raise StagingArtifactError("staging root must be a real directory, not a symlink")
        self.root = raw_root.resolve(strict=True)

    def _directory(self, parts: tuple[str, ...], *, create: bool) -> Path | None:
        current = self.root
        for part in parts:
            current = current / part
            if create:
                try:
                    current.mkdir(mode=0o700)
                except FileExistsError:
                    pass
            try:
                info = current.lstat()
            except FileNotFoundError:
                return None
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise StagingArtifactError("artifact directory contains a symlink or non-directory")
            if not current.resolve(strict=True).is_relative_to(self.root):
                raise StagingArtifactError("artifact directory escapes the staging root")
        return current

    def _attempt_directory(
        self,
        area: str,
        job_id: uuid.UUID,
        fencing_token: int,
        *,
        create: bool,
    ) -> Path | None:
        if area not in {"staging", "published"}:
            raise StagingArtifactError("unsupported artifact area")
        if not isinstance(job_id, uuid.UUID):
            raise StagingArtifactError("job_id must be a UUID")
        _validate_positive_int(fencing_token, "fencing_token")
        return self._directory((area, str(job_id), str(fencing_token)), create=create)

    def _metadata_path(
        self,
        metadata: ArtifactMetadata,
        *,
        expected_area: str | None = None,
    ) -> Path:
        if not isinstance(metadata, ArtifactMetadata):
            raise StagingArtifactError("metadata must be an ArtifactMetadata value")
        if not isinstance(metadata.job_id, uuid.UUID):
            raise StagingArtifactError("job_id must be a UUID")
        _validate_artifact_name(metadata.artifact_name)
        _validate_positive_int(metadata.fencing_token, "fencing_token")
        _validate_positive_int(metadata.byte_length, "byte_length")
        _validate_media_type(metadata.media_type)
        if not isinstance(metadata.sha256, str) or _SHA256_RE.fullmatch(metadata.sha256) is None:
            raise StagingArtifactError("sha256 must be 64 lowercase hexadecimal characters")
        if expected_area is not None and expected_area not in {"staging", "published"}:
            raise StagingArtifactError("unsupported expected artifact area")
        expected_prefixes = (expected_area,) if expected_area else ("staging", "published")
        expected = None
        for area in expected_prefixes:
            candidate = PurePosixPath(area, str(metadata.job_id), str(metadata.fencing_token), metadata.artifact_name)
            if metadata.relative_path == candidate.as_posix():
                expected = candidate
                break
        if expected is None:
            raise StagingArtifactError("relative_path does not match the job, fencing token and artifact name")
        directory = self._directory(
            (str(expected.parts[0]), str(metadata.job_id), str(metadata.fencing_token)),
            create=False,
        )
        if directory is None:
            raise StagingArtifactError("artifact attempt directory does not exist")
        path = directory / metadata.artifact_name
        if not path.resolve(strict=False).is_relative_to(self.root):
            raise StagingArtifactError("artifact path escapes the staging root")
        return path

    def _write_immutable(
        self,
        directory: Path,
        artifact_name: str,
        *,
        max_bytes: int,
        data_source: Path | None,
        data: bytes | None,
    ) -> Path:
        """Atomically create a new directory entry without replacing an existing artifact."""
        _validate_artifact_name(artifact_name)
        _validate_positive_int(max_bytes, "max_bytes")
        temporary = directory / f".{artifact_name}.{uuid.uuid4().hex}.tmp"
        destination = directory / artifact_name
        fd: int | None = None
        try:
            if data is not None:
                if len(data) > max_bytes:
                    raise StagingArtifactError("artifact exceeds the explicit max_bytes limit")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(temporary, flags, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    fd = None
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            elif data_source is not None:
                source_fd = os.open(
                    data_source,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                )
                try:
                    source_info = os.fstat(source_fd)
                    if not stat.S_ISREG(source_info.st_mode):
                        raise StagingArtifactError("staged artifact is not a regular file")
                    temp_fd = os.open(
                        temporary,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                    )
                    total = 0
                    with os.fdopen(source_fd, "rb", closefd=True) as source, os.fdopen(
                        temp_fd, "wb", closefd=True
                    ) as target:
                        source_fd = -1
                        while chunk := source.read(_COPY_CHUNK_SIZE):
                            total += len(chunk)
                            if total > max_bytes:
                                raise StagingArtifactError(
                                    "artifact exceeds the explicit max_bytes limit during publication"
                                )
                            target.write(chunk)
                        target.flush()
                        os.fsync(target.fileno())
                finally:
                    if source_fd >= 0:
                        os.close(source_fd)
            else:
                raise StagingArtifactError("either data or data_source must be supplied")

            # Hard-link creation is atomic and fails instead of replacing a prior file.
            os.link(temporary, destination)
            return destination
        except FileExistsError as exc:
            raise StagingArtifactError("artifact already exists for this attempt") from exc
        finally:
            if fd is not None:
                os.close(fd)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def stage_artifact(
        self,
        *,
        job_id: uuid.UUID,
        fencing_token: int,
        artifact_name: str,
        data: bytes,
        media_type: str,
        max_bytes: int,
        expected_sha256: str | None = None,
    ) -> ArtifactMetadata:
        """Write and fsync one artifact under a unique, fenced staging directory."""
        _validate_artifact_name(artifact_name)
        _validate_media_type(media_type)
        _validate_positive_int(fencing_token, "fencing_token")
        _validate_positive_int(max_bytes, "max_bytes")
        if not isinstance(job_id, uuid.UUID):
            raise StagingArtifactError("job_id must be a UUID")
        if not isinstance(data, bytes):
            raise StagingArtifactError("data must be bytes")
        if len(data) > max_bytes:
            raise StagingArtifactError("artifact exceeds the explicit max_bytes limit")
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 is not None and expected_sha256 != digest:
            raise StagingArtifactError("artifact checksum does not match expected_sha256")

        directory = self._attempt_directory("staging", job_id, fencing_token, create=True)
        assert directory is not None
        self._write_immutable(
            directory,
            artifact_name,
            max_bytes=max_bytes,
            data_source=None,
            data=data,
        )
        return ArtifactMetadata(
            job_id=job_id,
            fencing_token=fencing_token,
            artifact_name=artifact_name,
            relative_path=PurePosixPath(
                "staging", str(job_id), str(fencing_token), artifact_name
            ).as_posix(),
            byte_length=len(data),
            sha256=digest,
            media_type=media_type,
        )

    def verify_artifact(self, metadata: ArtifactMetadata, *, max_bytes: int) -> ArtifactMetadata:
        """Verify path, regular-file type, exact length and SHA-256 without following symlinks."""
        _validate_positive_int(max_bytes, "max_bytes")
        path = self._metadata_path(metadata)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except OSError as exc:
            raise StagingArtifactError("artifact cannot be opened safely") from exc
        digest = hashlib.sha256()
        total = 0
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise StagingArtifactError("artifact is not a regular file")
            while chunk := os.read(fd, _COPY_CHUNK_SIZE):
                total += len(chunk)
                if total > max_bytes:
                    raise StagingArtifactError("artifact exceeds the explicit max_bytes limit")
                digest.update(chunk)
        finally:
            os.close(fd)
        if total != metadata.byte_length:
            raise StagingArtifactError("artifact byte_length does not match the stored file")
        if digest.hexdigest() != metadata.sha256:
            raise StagingArtifactError("artifact checksum does not match the stored file")
        return metadata

    async def publish_staged_artifact(
        self,
        session: AsyncSession,
        *,
        lease: IngestionJobLease,
        metadata: ArtifactMetadata,
        now: datetime,
        max_bytes: int,
    ) -> ArtifactMetadata:
        """Publish only under the current live DB lease; caller owns commit/rollback.

        The published path remains attempt-scoped and immutable. If the caller later
        rolls back its DB transaction, the file is an unreferenced orphan and can be
        removed explicitly with discard_attempt(remove_published=True).
        """
        _validate_now(now)
        _validate_positive_int(max_bytes, "max_bytes")
        if metadata.job_id != lease.job_id or metadata.fencing_token != lease.fencing_token:
            raise StaleArtifactAttemptError("artifact metadata does not belong to the supplied lease")
        self.verify_artifact(metadata, max_bytes=max_bytes)
        result = await session.execute(
            select(IngestionJob)
            .where(
                IngestionJob.id == lease.job_id,
                IngestionJob.status == "running",
                IngestionJob.lease_owner == lease.worker_id,
                IngestionJob.lease_token == lease.lease_token,
                IngestionJob.fencing_token == lease.fencing_token,
                IngestionJob.lease_expires_at.is_not(None),
                IngestionJob.lease_expires_at > now,
                IngestionJob.cancellation_requested.is_(False),
            )
            .with_for_update()
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise StaleArtifactAttemptError("job lease is stale, expired, cancelled or no longer running")

        directory = self._attempt_directory(
            "published", metadata.job_id, metadata.fencing_token, create=True
        )
        assert directory is not None
        published = replace(
            metadata,
            relative_path=PurePosixPath(
                "published", str(metadata.job_id), str(metadata.fencing_token), metadata.artifact_name
            ).as_posix(),
        )
        try:
            self._write_immutable(
                directory,
                metadata.artifact_name,
                max_bytes=max_bytes,
                data_source=self._metadata_path(metadata, expected_area="staging"),
                data=None,
            )
        except StagingArtifactError as exc:
            if str(exc) != "artifact already exists for this attempt":
                raise
            self.verify_artifact(published, max_bytes=max_bytes)
        self.verify_artifact(published, max_bytes=max_bytes)
        return published

    def discard_attempt(
        self,
        *,
        job_id: uuid.UUID,
        fencing_token: int,
        remove_published: bool,
    ) -> None:
        """Idempotently remove one explicitly named attempt; never runs automatically."""
        _validate_positive_int(fencing_token, "fencing_token")
        if not isinstance(job_id, uuid.UUID):
            raise StagingArtifactError("job_id must be a UUID")
        areas = ("staging", "published") if remove_published else ("staging",)
        for area in areas:
            directory = self._attempt_directory(area, job_id, fencing_token, create=False)
            if directory is not None:
                shutil.rmtree(directory)
