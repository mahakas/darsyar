"""R-1: enforce ON DELETE RESTRICT on outbox.job_id → ingestion_jobs.id.

Revision ID: 0019_outbox_job_fk_restrict
Revises: 0018_ingestion_persistence
Create Date: 2026-11-10

Owner decision R-1 = OPTION_B (ON DELETE RESTRICT). This migration changes only
the foreign key `fk_outbox_events_job` from CASCADE to RESTRICT so that deleting
an ingestion job is prevented while associated outbox history remains (R-2).

No data migration; no row deletion; table/column names and data preserved.
Reversible: downgrade restores ON DELETE CASCADE.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0019_outbox_job_fk_restrict"
down_revision: str | None = "0018_ingestion_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_outbox_events_job", "outbox_events", type_="foreignkey")
    op.create_foreign_key(
        "fk_outbox_events_job",
        "outbox_events",
        "ingestion_jobs",
        ["job_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_outbox_events_job", "outbox_events", type_="foreignkey")
    op.create_foreign_key(
        "fk_outbox_events_job",
        "outbox_events",
        "ingestion_jobs",
        ["job_id"],
        ["id"],
        ondelete="CASCADE",
    )
