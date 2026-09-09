"""Align the migrated core with its existing ORM constraints.

Revision ID: 20260907_000002
Revises: 20260707_000001
"""

import sqlalchemy as sa
from alembic import op

revision = "20260907_000002"
down_revision = "20260707_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    orphan = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM tenants t LEFT JOIN users u ON u.uuid = t.owner_id "
            "WHERE t.owner_id IS NOT NULL AND u.uuid IS NULL)"
        )
    )
    if orphan:
        raise RuntimeError("Cannot add tenant owner FK: repair orphan owner references before retrying")
    # Each column already has a unique index; removing the duplicate constraint
    # preserves uniqueness while bringing Alembic into parity with the ORM.
    op.drop_constraint("email_addresses_email_key", "email_addresses", type_="unique")
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.drop_constraint("tenants_slug_key", "tenants", type_="unique")
    op.create_foreign_key("fk_tenants_owner_id", "tenants", "users", ["owner_id"], ["uuid"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_tenants_owner_id", "tenants", type_="foreignkey")
    op.create_unique_constraint("tenants_slug_key", "tenants", ["slug"])
    op.create_unique_constraint("users_username_key", "users", ["username"])
    op.create_unique_constraint("email_addresses_email_key", "email_addresses", ["email"])
