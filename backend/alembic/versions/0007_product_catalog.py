"""Create product_catalog with initial Basic/Pro records (slice B, ADR-047).

Revision ID: 0007_product_catalog
Revises: 0006_payment_transactions
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_product_catalog"
down_revision: str | None = "0006_payment_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_catalog",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("price_toman", sa.Integer(), nullable=False),
        sa.Column("credit_grant", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("price_toman > 0", name="ck_product_catalog_price_positive"),
        sa.CheckConstraint("credit_grant > 0", name="ck_product_catalog_grant_positive"),
    )
    op.create_index("uq_product_catalog_product_id", "product_catalog", ["product_id"], unique=True)

    op.execute(
        sa.text(
            """
            INSERT INTO product_catalog (product_id, price_toman, credit_grant)
            VALUES ('basic', 500000, 500), ('pro', 1000000, 1200);
            """
        )
    )


def downgrade() -> None:
    op.drop_table("product_catalog")
