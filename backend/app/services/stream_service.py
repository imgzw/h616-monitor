import logging

import httpx

from app.config import settings
from app.services.transcode_service import transcode_service

logger = logging.getLogger(__name__)


class StreamService:
    """Checks go2rtc stream availability and constructs stream URLs."""

    def __init__(self):
        self._base_url = f"http://{settings.go2rtc_host}:{settings.go2rtc_port}"

    async def is_active(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/api/streams")
                if resp.status_code == 200:
                    streams = resp.json()
                    return settings.camera_name in [s.get("name") or s for s in streams] if isinstance(streams, list) else False
                return False
        except Exception:
            return False

    async def get_stream_url(self, protocol: str = "webrtc") -> str:
        host = settings.go2rtc_host
        port = settings.go2rtc_port
        name = settings.camera_name

        match protocol:
            case "webrtc":
                return f"{host}:{port}/api/webrtc?src={name}"
            case "mjpeg":
                return f"http://{host}:{port}/api/stream.mjpeg?src={name}"
            case "hls":
                return f"http://{host}:{port}/api/stream.hls?src={name}"
            case _:
                return f"{host}:{port}/api/webrtc?src={name}"

    async def get_low_bandwidth_url(self, protocol: str = "webrtc") -> dict:
        if not transcode_service.available:
            return {"available": False, "url": "", "protocol": protocol}

        stream_name = settings.low_bandwidth_stream_name
        host = settings.go2rtc_host
        port = settings.go2rtc_port

        match protocol:
            case "webrtc":
                url = f"{host}:{port}/api/webrtc?src={stream_name}"
            case "hls":
                url = f"http://{host}:{port}/api/stream.hls?src={stream_name}"
            case _:
                url = f"{host}:{port}/api/webrtc?src={stream_name}"

        return {
            "available": True,
            "url": url,
            "protocol": protocol,
            "stream_name": stream_name,
            "encoder": transcode_service.encoder,
            "hw_accelerated": transcode_service.hw_accelerated,
        }


stream_service = StreamService()