"""knowledge_base_group_permissions

Revision ID: 5a5145bdde5a
Revises: 3f8c2625f16e
Create Date: 2026-08-01 04:57:27.607670
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '5a5145bdde5a'
down_revision: str | None = '3f8c2625f16e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_group_permissions",
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column(
            "permission_level", sa.String(length=16), nullable=False, server_default="read"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["groups.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("knowledge_base_id", "group_id"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_base_group_permissions")
