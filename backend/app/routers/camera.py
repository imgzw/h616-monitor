import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.models import CameraControl, CameraInfo, SetControlRequest
from app.services.camera_control import camera_control
from app.services.stream_service import stream_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/info", response_model=CameraInfo)
async def get_camera_info():
    info, resolution, formats = await asyncio.gather(
        camera_control.get_info(),
        camera_control.get_resolution(),
        camera_control.get_formats(),
    )
    return CameraInfo(
        device=info.get("device", ""),
        card=info.get("card", "Unknown"),
        driver=info.get("driver", "Unknown"),
        bus_info=info.get("bus_info", "Unknown"),
        resolution=resolution,
        formats=formats,
    )


@router.get("/controls", response_model=list[CameraControl])
async def list_controls():
    controls = await camera_control.list_controls()
    return [CameraControl(**c) for c in controls]


@router.get("/control/{name}")
async def get_control(name: str):
    ctrl = await camera_control.get_control(name)
    if ctrl is None:
        raise HTTPException(status_code=404, detail=f"Control '{name}' not found")
    return ctrl


@router.put("/control/{name}")
async def set_control(name: str, body: SetControlRequest):
    success = await camera_control.set_control(name, body.value)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to set '{name}'")
    ctrl = await camera_control.get_control(name)
    return ctrl


@router.post("/zoom/in")
async def zoom_in(step: int = 1):
    result = await camera_control.zoom_in(step)
    if result is None:
        raise HTTPException(status_code=400, detail="Zoom control not available")
    return {"zoom": result}


@router.post("/zoom/out")
async def zoom_out(step: int = 1):
    result = await camera_control.zoom_out(step)
    if result is None:
        raise HTTPException(status_code=400, detail="Zoom control not available")
    return {"zoom": result}


@router.post("/zoom/set")
async def zoom_set(value: int):
    result = await camera_control.zoom_set(value)
    if result is None:
        raise HTTPException(status_code=400, detail="Zoom control not available")
    return {"zoom": result}


@router.get("/stream-url")
async def get_stream_url(protocol: str = "webrtc"):
    url = await stream_service.get_stream_url(protocol)
    return {"url": url, "protocol": protocol}


@router.get("/low-bandwidth-url")
async def get_low_bandwidth_url(protocol: str = "webrtc"):
    result = await stream_service.get_low_bandwidth_url(protocol)
    if not result["available"]:
        raise HTTPException(
            status_code=503,
            detail="Low-bandwidth streaming not available: no H.264 encoder found",
        )
    return result