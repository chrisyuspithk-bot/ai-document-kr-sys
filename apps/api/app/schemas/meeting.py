"""Pydantic schemas for meeting intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Meeting ───────────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    meeting_date: datetime | None = None
    folder: str | None = Field(None, max_length=200)
    tags: list[str] | None = None


class MeetingUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = None
    meeting_date: datetime | None = None
    folder: str | None = Field(None, max_length=200)
    tags: list[str] | None = None


class MeetingListItem(BaseModel):
    id: uuid.UUID
    title: str
    meeting_date: datetime | None
    folder: str | None
    status: str
    created_at: datetime
    recording_count: int = 0
    has_transcript: bool = False
    has_summary: bool = False

    model_config = {"from_attributes": True}


class MeetingRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    description: str | None
    meeting_date: datetime | None
    folder: str | None
    tags: list | None
    status: str
    created_by: uuid.UUID
    linked_kb_ids: list | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Recording ─────────────────────────────────────────────────────────

class RecordingRead(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    filename: str
    file_size: int | None
    duration_seconds: float | None
    format: str | None
    language: str | None
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Transcript ────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None
    language: str | None = None


class TranscriptRead(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    recording_id: uuid.UUID | None
    full_text: str
    segments: list[dict] | None
    language: str | None
    confidence: float | None
    asr_provider: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptSegmentsResponse(BaseModel):
    segments: list[dict]
    language: str | None


# ── Summary ───────────────────────────────────────────────────────────

class SummaryRead(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    summary: str | None
    decisions: list | None
    action_items: list | None
    key_points: list | None
    model: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MeetingDetail(BaseModel):
    """Full meeting detail with recordings, transcript, and summary."""
    meeting: MeetingRead
    recordings: list[RecordingRead] = []
    transcript: TranscriptRead | None = None
    summary: SummaryRead | None = None


# ── Link KB ───────────────────────────────────────────────────────────

class LinkKbRequest(BaseModel):
    kb_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
