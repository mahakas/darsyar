"""Make the administrative audit log immutable in PostgreSQL (R-122).

Revision ID: 0023_admin_audit_append_only
Revises: 0022_users_selected_grade

The actor FK becomes RESTRICT so hard deletion cannot mutate an immutable audit row.
Normal account removal remains a soft delete (users.deleted_at).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023_admin_audit_append_only"
down_revision: str | None = "0022_users_selected_grade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_admin_audit_log_actor", "admin_audit_log", type_="foreignkey")
    op.create_foreign_key(
        "fk_admin_audit_log_actor",
        "admin_audit_log",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION darsyar_reject_admin_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'admin_audit_log is append-only'
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_admin_audit_log_no_row_mutation
        BEFORE UPDATE OR DELETE ON admin_audit_log
        FOR EACH ROW
        EXECUTE FUNCTION darsyar_reject_admin_audit_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_admin_audit_log_no_truncate
        BEFORE TRUNCATE ON admin_audit_log
        FOR EACH STATEMENT
        EXECUTE FUNCTION darsyar_reject_admin_audit_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_admin_audit_log_no_truncate ON admin_audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_admin_audit_log_no_row_mutation ON admin_audit_log")
    op.execute("DROP FUNCTION IF EXISTS darsyar_reject_admin_audit_mutation()")
    op.drop_constraint("fk_admin_audit_log_actor", "admin_audit_log", type_="foreignkey")
    op.create_foreign_key(
        "fk_admin_audit_log_actor",
        "admin_audit_log",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
