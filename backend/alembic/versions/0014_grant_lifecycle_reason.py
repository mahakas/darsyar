"""Grant lifecycle reason + effective timestamp (OQ-028).

Revision ID: 0014_grant_lifecycle_reason
Revises: 0013_grant_allocation
Create Date: 2026-10-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_grant_lifecycle_reason"
down_revision: str | None = "0013_grant_allocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOWED_REASONS = ("natural_expiry", "immediate_cancellation", "approved_refund", "admin_void")


def upgrade() -> None:
    op.add_column("credit_grants", sa.Column("lifecycle_reason", sa.String(length=32), nullable=True))
    op.add_column("credit_grants", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_credit_grants_lifecycle_reason_valid",
        "credit_grants",
        "lifecycle_reason IS NULL OR lifecycle_reason IN ('natural_expiry','immediate_cancellation','approved_refund','admin_void')",
    )
    op.create_check_constraint(
        "ck_credit_grants_voided_at_consistent",
        "credit_grants",
        "(lifecycle_reason IS NULL) = (voided_at IS NULL)",
    )


def downgrade() -> None:
    """forward-only (هم‌سبک 0012/0013): رد پیش از هر DDL.

    0014 تاریخچهٔ دلیل چرخهٔ حیات (lifecycle_reason/voided_at) را نگه می‌دارد؛
    downgrade آن‌ها و CHECKهای مربوط را نابود می‌کند.
    """
    raise RuntimeError(
        "migration 0014 is forward-only: downgrade is rejected before any DDL "
        "because it would destroy grant lifecycle-reason history."
    )
