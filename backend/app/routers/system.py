import asyncio
import time

from fastapi import APIRouter

from app.config import settings
from app.models import CPUTempInfo, RecordingStatus, StorageInfo, SystemStatus, TranscodeInfo
from app.services.disk_manager import disk_manager
from app.services.recorder import recorder
from app.services.stream_service import stream_service
from app.services.transcode_service import transcode_service

router = APIRouter(prefix="/api", tags=["system"])

_start_time = time.time()


async def _read_cpu_temp() -> CPUTempInfo:
    try:
        with open(settings.thermal_zone_path) as f:
            temp_mc = int(f.read().strip())
        temp_c = temp_mc / 1000.0
    except (FileNotFoundError, ValueError, OSError):
        temp_c = -1.0

    return CPUTempInfo(
        temp_c=round(temp_c, 1),
        high_threshold=settings.temp_high_threshold,
        critical_threshold=settings.temp_critical_threshold,
        warning=temp_c >= settings.temp_high_threshold if temp_c >= 0 else False,
    )


@router.get("/status", response_model=SystemStatus)
async def system_status():
    storage, stream_active, cpu_temp = await asyncio.gather(
        disk_manager.get_storage_info(),
        stream_service.is_active(),
        _read_cpu_temp(),
    )
    return SystemStatus(
        stream_active=stream_active,
        recording=await _recording_status(),
        storage=StorageInfo(**storage),
        cpu_temp=cpu_temp,
        transcode=TranscodeInfo(**transcode_service.get_info()),
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@router.get("/storage", response_model=StorageInfo)
async def storage_info():
    return StorageInfo(**(await disk_manager.get_storage_info()))


@router.get("/temp", response_model=CPUTempInfo)
async def cpu_temp():
    return await _read_cpu_temp()


@router.get("/transcode", response_model=TranscodeInfo)
async def transcode_info():
    return TranscodeInfo(**transcode_service.get_info())


@router.post("/cleanup")
async def trigger_cleanup():
    deleted = await disk_manager.cleanup_if_needed()
    return {"deleted_files": deleted}


@router.get("/go2rtc-config")
async def go2rtc_config():
    return {
        "host": settings.go2rtc_host,
        "port": settings.go2rtc_port,
        "camera_name": settings.camera_name,
        "webrtc_url": await stream_service.get_stream_url("webrtc"),
        "mjpeg_url": await stream_service.get_stream_url("mjpeg"),
        "low_bandwidth_url": await stream_service.get_low_bandwidth_url("webrtc"),
    }


async def _recording_status():
    return RecordingStatus(
        is_recording=recorder.is_recording,
        started_at=recorder.started_at,
        segment_duration=settings.segment_duration,
        pid=recorder.pid,
    )