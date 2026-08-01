"""add meetings, recordings, transcripts, summaries

Revision ID: ab80b333e819
Revises: dfd920aaaf81
Create Date: 2026-08-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ab80b333e819"
down_revision: str | None = "dfd920aaaf81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("meeting_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("folder", sa.String(length=200), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("linked_kb_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meetings_org_id"), "meetings", ["org_id"])

    op.create_table(
        "meeting_recordings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("format", sa.String(length=20), nullable=True),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meeting_recordings_meeting_id"), "meeting_recordings", ["meeting_id"])
    op.create_index(op.f("ix_meeting_recordings_org_id"), "meeting_recordings", ["org_id"])

    op.create_table(
        "meeting_transcripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("recording_id", sa.Uuid(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("asr_provider", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["recording_id"], ["meeting_recordings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id"),
    )
    op.create_index(op.f("ix_meeting_transcripts_meeting_id"), "meeting_transcripts", ["meeting_id"], unique=True)
    op.create_index(op.f("ix_meeting_transcripts_org_id"), "meeting_transcripts", ["org_id"])

    op.create_table(
        "meeting_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("decisions", sa.JSON(), nullable=True),
        sa.Column("action_items", sa.JSON(), nullable=True),
        sa.Column("key_points", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id"),
    )
    op.create_index(op.f("ix_meeting_summaries_meeting_id"), "meeting_summaries", ["meeting_id"], unique=True)
    op.create_index(op.f("ix_meeting_summaries_org_id"), "meeting_summaries", ["org_id"])


def downgrade() -> None:
    op.drop_table("meeting_summaries")
    op.drop_table("meeting_transcripts")
    op.drop_table("meeting_recordings")
    op.drop_table("meetings")
