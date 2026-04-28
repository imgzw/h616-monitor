import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class StreamService:

    def __init__(self):
        self._base_url = f"http://{settings.go2rtc_host}:{settings.go2rtc_port}"

    async def is_active(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/api/streams")
                if resp.status_code != 200:
                    return False
                streams = resp.json()
                if isinstance(streams, dict):
                    return settings.camera_name in streams
                if isinstance(streams, list):
                    return settings.camera_name in [s.get("name") or s for s in streams]
                return False
        except Exception:
            return False

    async def get_stream_url(self, protocol: str = "webrtc") -> str:
        name = settings.camera_name
        return _stream_url(name, protocol)

    async def get_low_bandwidth_url(self, protocol: str = "mjpeg") -> dict:
        return {
            "available": True,
            "url": "/api/stream.mjpeg?src=camera",
            "protocol": "mjpeg",
            "stream_name": "camera",
            "encoder": "mjpeg",
            "hw_accelerated": False,
        }


def _stream_url(name: str, protocol: str) -> str:
    match protocol:
        case "webrtc":
            return f"/api/webrtc?src={name}"
        case "mjpeg":
            return f"/api/stream.mjpeg?src={name}"
        case "hls":
            return f"/api/stream.hls?src={name}"
        case _:
            return f"/api/webrtc?src={name}"


stream_service = StreamService()