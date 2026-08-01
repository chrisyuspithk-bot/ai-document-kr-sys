"""Meeting intelligence endpoints: upload, transcribe, summarize, link to KB."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, require_permission
from app.core.exceptions import bad_request, not_found
from app.models.meeting import (
    RECORDING_STATUS_PENDING,
    Meeting,
    MeetingRecording,
    MeetingSummary,
    MeetingTranscript,
)
from app.models.user import User
from app.schemas.meeting import (
    LinkKbRequest,
    MeetingCreate,
    MeetingDetail,
    MeetingListItem,
    MeetingRead,
    MeetingUpdate,
    RecordingRead,
    SummaryRead,
    TranscriptRead,
)
from app.services.audit_service import write_audit
from app.services.meeting import process_recording, save_uploaded_file, summarize_meeting
from app.services.permissions import MEETING_READ, MEETING_WRITE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meetings", tags=["meetings"])



# ── Meeting CRUD ──────────────────────────────────────────────────────

@router.get("", response_model=list[MeetingListItem])
async def list_meetings(
    folder: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_READ)),
):
    conditions = [Meeting.org_id == current_user.org_id]
    if folder:
        conditions.append(Meeting.folder == folder)
    if status_filter:
        conditions.append(Meeting.status == status_filter)
    if search:
        conditions.append(Meeting.title.ilike(f"%{search}%"))

    count_q = select(func.count(Meeting.id)).where(*conditions)
    (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    q = (
        select(Meeting)
        .where(*conditions)
        .options(
            selectinload(Meeting.recordings),
            selectinload(Meeting.transcript),
            selectinload(Meeting.summary),
        )
        .order_by(
            Meeting.meeting_date.desc().nullslast(), Meeting.created_at.desc()
        )
        .offset(offset)
        .limit(page_size)
    )
    meetings = (await db.execute(q)).scalars().all()

    return [
        MeetingListItem(
            id=m.id,
            title=m.title,
            meeting_date=m.meeting_date,
            folder=m.folder,
            status=m.status,
            created_at=m.created_at,
            recording_count=len(m.recordings),
            has_transcript=m.transcript is not None,
            has_summary=m.summary is not None,
        )
        for m in meetings
    ]


@router.post("", response_model=MeetingRead, status_code=201)
async def create_meeting(
    payload: MeetingCreate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_WRITE)),
):
    meeting = Meeting(
        org_id=current_user.org_id,
        title=payload.title,
        description=payload.description,
        meeting_date=payload.meeting_date,
        folder=payload.folder,
        tags=payload.tags,
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    await write_audit(
        db,
        action="meeting.created",
        actor_user_id=current_user.id,
        resource_id=str(meeting.id),
    )
    return meeting


@router.get("/{meeting_id}", response_model=MeetingDetail)
async def get_meeting(
    meeting_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_READ)),
):
    meeting = await _get_meeting(db, meeting_id, current_user.org_id)
    return MeetingDetail(
        meeting=MeetingRead.model_validate(meeting),
        recordings=[
            RecordingRead.model_validate(r) for r in meeting.recordings
        ],
        transcript=(
            TranscriptRead.model_validate(meeting.transcript)
            if meeting.transcript else None
        ),
        summary=(
            SummaryRead.model_validate(meeting.summary)
            if meeting.summary else None
        ),
    )


@router.patch("/{meeting_id}", response_model=MeetingRead)
async def update_meeting(
    meeting_id: uuid.UUID,
    payload: MeetingUpdate,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_WRITE)),
):
    meeting = await _get_meeting(db, meeting_id, current_user.org_id)
    for field in ("title", "description", "meeting_date", "folder", "tags"):
        if (val := getattr(payload, field, None)) is not None:
            setattr(meeting, field, val)
    await db.commit()
    await db.refresh(meeting)
    await write_audit(
        db,
        action="meeting.updated",
        actor_user_id=current_user.id,
        resource_id=str(meeting.id),
    )
    return meeting


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_WRITE)),
):
    meeting = await _get_meeting(db, meeting_id, current_user.org_id)
    await db.delete(meeting)
    await db.commit()
    await write_audit(
        db,
        action="meeting.deleted",
        actor_user_id=current_user.id,
        resource_id=str(meeting_id),
    )


# ── Recording upload & transcription ──────────────────────────────────

@router.post("/{meeting_id}/recordings", response_model=list[RecordingRead], status_code=201)
async def upload_recordings(
    meeting_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    language: str = Form("yue"),
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_WRITE)),
):
    meeting = await _get_meeting(db, meeting_id, current_user.org_id)

    if len(files) > 10:
        raise bad_request("Maximum 10 files per upload")

    recordings = []
    for f in files:
        content = await f.read()
        if not content:
            continue
        filepath = await save_uploaded_file(
            content, f.filename or "recording", current_user.org_id, meeting_id
        )
        recording = MeetingRecording(
            meeting_id=meeting_id,
            org_id=current_user.org_id,
            filename=f.filename or "recording",
            file_path=str(filepath),
            file_size=len(content),
            format=filepath.suffix.lstrip("."),
            language=language,
            status=RECORDING_STATUS_PENDING,
        )
        db.add(recording)
        recordings.append(recording)

    await db.commit()
    for r in recordings:
        await db.refresh(r)

    await write_audit(
        db,
        action="meeting.recordings_uploaded",
        actor_user_id=current_user.id,
        resource_id=str(meeting_id),
    )

    # Start async transcription for each recording
    for recording in recordings:
        await process_recording(recording, db, language=language)

    await db.refresh(meeting, ["recordings"])
    return [RecordingRead.model_validate(r) for r in meeting.recordings]


@router.get("/{meeting_id}/recordings/{recording_id}", response_model=RecordingRead)
async def get_recording(
    meeting_id: uuid.UUID,
    recording_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_READ)),
):
    recording = await db.get(MeetingRecording, recording_id)
    if (
        not recording
        or recording.meeting_id != meeting_id
        or recording.org_id != current_user.org_id
    ):
        raise not_found("Recording not found")
    return recording


# ── Transcript ────────────────────────────────────────────────────────

@router.get("/{meeting_id}/transcript", response_model=TranscriptRead)
async def get_transcript(
    meeting_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_READ)),
):
    _ = await _get_meeting(db, meeting_id, current_user.org_id)
    transcript = (
        await db.execute(
            select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
        )
    ).scalar_one_or_none()
    if not transcript:
        raise not_found("Transcript not found")
    return transcript


@router.get("/{meeting_id}/transcript/segments", response_model=dict)
async def get_transcript_segments(
    meeting_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_READ)),
):
    _ = await _get_meeting(db, meeting_id, current_user.org_id)
    transcript = (
        await db.execute(
            select(MeetingTranscript).where(MeetingTranscript.meeting_id == meeting_id)
        )
    ).scalar_one_or_none()
    if not transcript:
        raise not_found("Transcript not found")
    return {"segments": transcript.segments or [], "language": transcript.language}


# ── Summary ───────────────────────────────────────────────────────────

@router.post("/{meeting_id}/summarize", response_model=SummaryRead)
async def generate_summary(
    meeting_id: uuid.UUID,
    model: str | None = Query(None),
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_WRITE)),
):
    meeting = await _get_meeting(db, meeting_id, current_user.org_id)
    if not meeting.transcript or not meeting.transcript.full_text.strip():
        raise bad_request("Meeting has no transcript — upload and transcribe a recording first")

    summary = await summarize_meeting(meeting, db, model=model)
    await write_audit(
        db,
        action="meeting.summarized",
        actor_user_id=current_user.id,
        resource_id=str(meeting_id),
    )
    return summary


@router.get("/{meeting_id}/summary", response_model=SummaryRead)
async def get_summary(
    meeting_id: uuid.UUID,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_READ)),
):
    _ = await _get_meeting(db, meeting_id, current_user.org_id)
    summary = (
        await db.execute(
            select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
        )
    ).scalar_one_or_none()
    if not summary:
        raise not_found("Summary not found")
    return summary


# ── Link to Knowledge Base ────────────────────────────────────────────

@router.post("/{meeting_id}/link-kb", response_model=MeetingRead)
async def link_to_kb(
    meeting_id: uuid.UUID,
    payload: LinkKbRequest,
    db: DbSession = None,
    current_user: User = Depends(require_permission(MEETING_WRITE)),
):
    meeting = await _get_meeting(db, meeting_id, current_user.org_id)
    if not meeting.transcript or not meeting.transcript.full_text.strip():
        raise bad_request("Meeting has no transcript to link as knowledge source")

    existing = set(meeting.linked_kb_ids or [])
    existing.update(str(kid) for kid in payload.kb_ids)
    meeting.linked_kb_ids = list(existing)

    await db.commit()
    await db.refresh(meeting)
    await write_audit(
        db,
        action="meeting.linked_kb",
        actor_user_id=current_user.id,
        resource_id=str(meeting_id),
    )
    return meeting


# ── Helpers ───────────────────────────────────────────────────────────

async def _get_meeting(db, meeting_id: uuid.UUID, org_id: uuid.UUID) -> Meeting:
    q = (
        select(Meeting)
        .where(Meeting.id == meeting_id, Meeting.org_id == org_id)
        .options(
            selectinload(Meeting.recordings),
            selectinload(Meeting.transcript),
            selectinload(Meeting.summary),
        )
    )
    meeting = (await db.execute(q)).scalar_one_or_none()
    if not meeting:
        raise not_found("Meeting not found")
    return meeting
