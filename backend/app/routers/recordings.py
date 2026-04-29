import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.models import RecordingList, RecordingStatus
from app.services.disk_manager import disk_manager
from app.services.recorder import recorder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recordings", tags=["recordings"])


def _recording_path(path: str) -> Path:
    base = settings.recordings_dir.resolve()
    filepath = (base / path).resolve()
    try:
        filepath.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=404, detail="Recording not found")
    return filepath


@router.post("/start")
async def start_recording():
    success = await recorder.start()
    if not success:
        raise HTTPException(status_code=409, detail="Recording already in progress or failed to start")
    return {"status": "recording", "pid": recorder.pid}


@router.post("/stop")
async def stop_recording():
    success = await recorder.stop()
    if not success:
        raise HTTPException(status_code=409, detail="No recording in progress")
    return {"status": "stopped"}


@router.get("/status", response_model=RecordingStatus)
async def recording_status():
    return RecordingStatus(
        is_recording=recorder.is_recording,
        started_at=recorder.started_at,
        segment_duration=settings.segment_duration,
        pid=recorder.pid,
    )


@router.get("", response_model=RecordingList)
async def list_recordings(page: int = 1, page_size: int = 20, date: Optional[str] = None):
    result = await disk_manager.list_recordings(page, page_size, date)
    return RecordingList(**result)


@router.delete("/{path:path}")
async def delete_recording(path: str):
    success = await disk_manager.delete_recording(path)
    if not success:
        raise HTTPException(status_code=404, detail="Recording not found")
    return {"status": "deleted"}


@router.get("/download/{path:path}")
async def download_recording(path: str):
    filepath = _recording_path(path)
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(
        filepath,
        media_type="video/mp4",
        filename=filepath.name,
    )


@router.get("/thumbnail/{path:path}")
async def get_thumbnail(path: str):
    filepath = _recording_path(path)
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Recording not found")

    thumb_dir = settings.recordings_dir / ".thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    rel_path = filepath.relative_to(settings.recordings_dir.resolve()).as_posix()
    thumb_path = thumb_dir / f"{rel_path.replace('/', '__')}.jpg"

    if thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    cmd = [
        settings.ffmpeg_path,
        "-i", str(filepath),
        "-ss", "0",
        "-frames:v", "1",
        "-vf", f"scale={settings.thumbnail_width}:{settings.thumbnail_height}",
        "-y", str(thumb_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=10)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=500, detail="Thumbnail generation timed out")
    if proc.returncode != 0 or not thumb_path.exists():
        raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

    return FileResponse(thumb_path, media_type="image/jpeg")
