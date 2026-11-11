"""Slice 1: durable ingestion jobs + transactional outbox persistence.

Revision ID: 0018_ingestion_persistence
Revises: 0017_stream_lease_billable
Create Date: 2026-11-10

Entities:
- `ingestion_documents` (canonical R-157 identity; provenance/authorization kept separate)
- `ingestion_jobs` (durable job state; independent of R-156 resource lifecycle)
- `outbox_events` (transactional outbox; publisher/reconciliation is a later slice)
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_ingestion_persistence"
down_revision: str | None = "0017_stream_lease_billable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_STATUSES = ("queued", "running", "retry_waiting", "succeeded", "terminal_failure", "cancellation_requested", "cancelled")
OUTBOX_STATES = ("pending", "publishing", "published", "failed")


def upgrade() -> None:
    op.create_table(
        "ingestion_documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("edition_year", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("grade_level BETWEEN 1 AND 12", name="ck_ingestion_documents_grade_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checksum", "edition_year", "subject", "grade_level", name="uq_ingestion_documents_canonical"),
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("request_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fencing_token", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("retry_available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("cancellation_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued','running','retry_waiting','succeeded','terminal_failure','cancellation_requested','cancelled')", name="ck_ingestion_jobs_status_valid"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ingestion_jobs_attempt_nonneg"),
        sa.CheckConstraint("fencing_token >= 0", name="ck_ingestion_jobs_fencing_nonneg"),
        sa.ForeignKeyConstraint(["document_id"], ["ingestion_documents.id"], ondelete="RESTRICT", name="fk_ingestion_jobs_document"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "request_idempotency_key", name="uq_ingestion_jobs_request_idempotency"),
    )
    op.create_index("ix_ingestion_jobs_claim", "ingestion_jobs", ["status", "retry_available_at"])
    op.create_index("ix_ingestion_jobs_lease_expiry", "ingestion_jobs", ["lease_expires_at"])
    op.create_index("ix_ingestion_jobs_document", "ingestion_jobs", ["document_id"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("dedup_key", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("publication_state", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("publication_state IN ('pending','publishing','published','failed')", name="ck_outbox_events_state_valid"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_events_attempt_nonneg"),
        sa.ForeignKeyConstraint(["job_id"], ["ingestion_jobs.id"], ondelete="CASCADE", name="fk_outbox_events_job"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key", name="uq_outbox_events_dedup"),
    )
    op.create_index("ix_outbox_events_claim", "outbox_events", ["publication_state", "available_at"])
    op.create_index("ix_outbox_events_job", "outbox_events", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_job", table_name="outbox_events")
    op.drop_index("ix_outbox_events_claim", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_ingestion_jobs_document", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_lease_expiry", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_claim", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_table("ingestion_documents")
