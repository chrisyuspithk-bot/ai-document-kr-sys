"""Meeting intelligence models: meetings, recordings, transcripts, summaries."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

MEETING_STATUS_PROCESSING = "processing"
MEETING_STATUS_COMPLETED = "completed"
MEETING_STATUS_FAILED = "failed"

RECORDING_STATUS_PENDING = "pending"
RECORDING_STATUS_TRANSCRIBING = "transcribing"
RECORDING_STATUS_COMPLETED = "completed"
RECORDING_STATUS_FAILED = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    folder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=MEETING_STATUS_COMPLETED, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    linked_kb_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    recordings: Mapped[list[MeetingRecording]] = relationship(
        "MeetingRecording", back_populates="meeting", cascade="all, delete-orphan"
    )
    transcript: Mapped[MeetingTranscript | None] = relationship(
        "MeetingTranscript", back_populates="meeting", uselist=False, cascade="all, delete-orphan"
    )
    summary: Mapped[MeetingSummary | None] = relationship(
        "MeetingSummary", back_populates="meeting", uselist=False, cascade="all, delete-orphan"
    )


class MeetingRecording(Base):
    __tablename__ = "meeting_recordings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True, default="yue")
    status: Mapped[str] = mapped_column(
        String(20), default=RECORDING_STATUS_PENDING, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="recordings")


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    recording_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meeting_recordings.id", ondelete="SET NULL"), nullable=True
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    segments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    asr_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="transcript")


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    decisions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    action_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    key_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="summary")
