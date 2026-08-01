"""Meeting intelligence service: transcription orchestration and summarization."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from app.models.meeting import (
    RECORDING_STATUS_COMPLETED,
    RECORDING_STATUS_FAILED,
    RECORDING_STATUS_TRANSCRIBING,
    Meeting,
    MeetingRecording,
    MeetingSummary,
    MeetingTranscript,
)
from app.services.asr import AUDIO_UPLOAD_DIR, AsrResult, get_asr_provider, validate_audio_file
from app.services.llm import LlmMessage, get_provider_for

logger = logging.getLogger(__name__)

_SUMMARIZE_SYSTEM = (
    "你是一個專業會議記錄分析助理，服務於仁愛堂社會服務部"
    "（Yan Oi Tong Social Services Division）。\n\n"
    "請根據提供的會議逐字稿，產生以下內容：\n"
    "1. 會議摘要（summary）：200–400 字概括會議內容\n"
    "2. 決定事項（decisions）：列出會議中作出的各項決定\n"
    "3. 行動項目（action_items）：列出各項待辦事項，包含負責人和截止日期（如有提及）\n"
    "4. 重點摘要（key_points）：列出 5-8 個關鍵要點\n\n"
    "使用繁體中文，專有名詞可保留英文。\n"
    "返回 JSON 格式：{\"summary\": \"...\", \"decisions\": [...], "
    "\"action_items\": [...], \"key_points\": [...]}"
)


async def process_recording(
    recording: MeetingRecording,
    db_session,
    language: str | None = None,
) -> AsrResult | None:
    """Transcribe a recording and store the transcript.

    Updates recording status through the pipeline: pending → transcribing → completed/failed.
    """
    recording.status = RECORDING_STATUS_TRANSCRIBING
    await db_session.commit()

    try:
        provider = get_asr_provider()
        result = await provider.transcribe(recording.file_path, language=language)

        await _store_transcript(db_session, recording, result)
        recording.status = RECORDING_STATUS_COMPLETED
        await db_session.commit()

        logger.info(
            "Transcription complete: recording=%s provider=%s duration=%.1fs",
            recording.id,
            provider.provider_name,
            result.duration_seconds or 0,
        )
        return result
    except Exception as exc:
        logger.exception("Transcription failed: recording=%s", recording.id)
        recording.status = RECORDING_STATUS_FAILED
        recording.error_message = str(exc)[:2000]
        await db_session.commit()
        return None


async def summarize_meeting(
    meeting: Meeting,
    db_session,
    model: str | None = None,
) -> MeetingSummary:
    """Generate meeting summary from transcript using LLM."""
    transcript = meeting.transcript
    if not transcript or not transcript.full_text:
        raise ValueError("Meeting has no transcript to summarize")

    text = transcript.full_text
    if len(text) > 12000:
        text = text[:12000] + "\n\n[... transcript truncated ...]"

    provider, _info = get_provider_for(
        model or os.getenv("SUMMARIZE_MODEL", "deepseek-chat"),
    )

    response = await provider.chat([
        LlmMessage(role="system", content=_SUMMARIZE_SYSTEM),
        LlmMessage(role="user", content=f"會議逐字稿：\n\n{text}"),
    ])

    try:
        data = _parse_summary_json(response.content)
    except (json.JSONDecodeError, KeyError):
        data = {
            "summary": response.content[:500],
            "decisions": [],
            "action_items": [],
            "key_points": [],
        }

    summary = MeetingSummary(
        meeting_id=meeting.id,
        org_id=meeting.org_id,
        summary=data.get("summary"),
        decisions=data.get("decisions"),
        action_items=data.get("action_items"),
        key_points=data.get("key_points"),
        model=response.model or model,
        prompt_tokens=response.usage.prompt_tokens if response.usage else None,
        completion_tokens=response.usage.completion_tokens if response.usage else None,
    )
    db_session.add(summary)
    await db_session.commit()
    await db_session.refresh(summary)

    logger.info("Summary generated: meeting=%s model=%s", meeting.id, response.model)
    return summary


async def _store_transcript(
    db_session,
    recording: MeetingRecording,
    result: AsrResult,
) -> MeetingTranscript:
    """Create or update transcript for the meeting."""
    from sqlalchemy import select

    stmt = select(MeetingTranscript).where(
        MeetingTranscript.meeting_id == recording.meeting_id
    )
    existing = (await db_session.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.full_text = result.full_text
        existing.segments = result.segments
        existing.language = result.language
        existing.confidence = result.confidence
        existing.asr_provider = result.provider
        existing.recording_id = recording.id
        transcript = existing
    else:
        transcript = MeetingTranscript(
            meeting_id=recording.meeting_id,
            org_id=recording.org_id,
            recording_id=recording.id,
            full_text=result.full_text,
            segments=result.segments,
            language=result.language,
            confidence=result.confidence,
            asr_provider=result.provider,
        )
        db_session.add(transcript)

    await db_session.commit()
    await db_session.refresh(transcript)
    return transcript


def _parse_summary_json(content: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.endswith("```"):
            content = content[:-3]
    return json.loads(content)


async def save_uploaded_file(
    file_content: bytes,
    filename: str,
    org_id: uuid.UUID,
    meeting_id: uuid.UUID,
) -> Path:
    """Save uploaded audio file to disk and return the path."""
    dir_path = AUDIO_UPLOAD_DIR / str(org_id) / str(meeting_id)
    dir_path.mkdir(parents=True, exist_ok=True)

    safe_name = Path(filename).name
    dest = dir_path / safe_name
    counter = 1
    while dest.exists():
        stem = Path(filename).stem
        ext = Path(filename).suffix
        dest = dir_path / f"{stem}_{counter}{ext}"
        counter += 1

    dest.write_bytes(file_content)
    validate_audio_file(str(dest))
    return dest
