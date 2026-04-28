import asyncio
import logging
import re
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

V4L2_M2M_ENCODER = "h264_v4l2m2m"
FALLBACK_ENCODER = "libx264"
FALLBACK_PRESET = "ultrafast"
FALLBACK_TUNE = "zerolatency"
LOW_STREAM_NAME = "camera_low"
H264_STREAM_NAME = "camera_h264"

V4L2_M2M_DEVICES = [
    "/dev/video32",
    "/dev/video33",
    "/dev/video34",
    "/dev/video35",
]


class TranscodeService:
    """Detects V4L2 M2M H.264 encoding capability and provides transcode info."""

    def __init__(self):
        self._available_encoders: list[str] = []
        self._hw_accelerated: bool = False
        self._selected_encoder: str = ""
        self._v4l2_m2m_available: bool = False
        self._initialized: bool = False

    @property
    def available(self) -> bool:
        return self._initialized and bool(self._selected_encoder)

    @property
    def encoder(self) -> str:
        return self._selected_encoder

    @property
    def hw_accelerated(self) -> bool:
        return self._hw_accelerated

    @property
    def stream_name(self) -> str:
        return LOW_STREAM_NAME

    @property
    def h264_stream_name(self) -> str:
        return H264_STREAM_NAME

    async def initialize(self) -> None:
        self._available_encoders = await self._detect_encoders()
        self._v4l2_m2m_available = self._check_v4l2_m2m_device()

        if V4L2_M2M_ENCODER in self._available_encoders and self._v4l2_m2m_available:
            self._selected_encoder = V4L2_M2M_ENCODER
            self._hw_accelerated = True
            logger.info(
                "V4L2 M2M hardware encoding available (encoder=%s)", V4L2_M2M_ENCODER
            )
        elif FALLBACK_ENCODER in self._available_encoders:
            self._selected_encoder = FALLBACK_ENCODER
            self._hw_accelerated = False
            logger.info(
                "Software H.264 encoding available (encoder=%s, preset=%s, tune=%s)",
                FALLBACK_ENCODER,
                FALLBACK_PRESET,
                FALLBACK_TUNE,
            )
        else:
            self._selected_encoder = ""
            logger.warning("No H.264 encoder available, transcoding disabled")

        self._initialized = True

    def get_go2rtc_stream_config(self) -> str:
        """Return go2rtc stream config line for transcoded streams.
        Returns empty string if no encoder available.
        Note: exec: format is used since ffmpeg runs as subprocess for H.264 encoding.
        V4L2 M2M is not available on H616 (cedrus is decoder-only), so libx264 is used.
        """
        if not self._selected_encoder:
            return ""

        vf = "scale=640:360" if self._hw_accelerated else "scale=640:360"
        params = f"-c:v {self._selected_encoder}"
        if not self._hw_accelerated:
            params += f" -preset {FALLBACK_PRESET} -tune {FALLBACK_TUNE}"
        if settings.low_bandwidth_bitrate:
            params += f" -b:v {settings.low_bandwidth_bitrate}"

        h264_cmd = (
            f'exec:ffmpeg -f v4l2 -input_format mjpeg '
            f'-video_size 1280x720 -framerate 15 -i {settings.camera_device} '
            f'-vf {vf} {params} -g 30 -f h264 pipe:1'
        )
        return h264_cmd

    async def _detect_encoders(self) -> list[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                settings.ffmpeg_path, "-encoders",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return []

            h264_encoders = []
            for line in stdout.decode(errors="replace").splitlines():
                if "h264" in line.lower() and "V" in line[:4]:
                    match = re.search(r"V[\s\.]+S[\s\.]+(\S+)", line)
                    if match:
                        name = match.group(1).strip()
                    else:
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[1]
                        else:
                            continue
                    if "h264" in name.lower():
                        h264_encoders.append(name)
            logger.info("Detected H.264 encoders: %s", h264_encoders)
            return h264_encoders
        except Exception:
            logger.exception("Failed to detect ffmpeg encoders")
            return []

    @staticmethod
    def _check_v4l2_m2m_device() -> bool:
        for dev in V4L2_M2M_DEVICES:
            if Path(dev).exists():
                return True

        try:
            import subprocess
            result = subprocess.run(
                ["v4l2-ctl", "--list-devices"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "m2m" in result.stdout.lower():
                return True
        except Exception:
            pass

        try:
            video_devices = list(Path("/dev").glob("video*"))
            if len(video_devices) > 1:
                return True
        except Exception:
            pass

        return False

    def get_info(self) -> dict:
        return {
            "available": self.available,
            "encoder": self._selected_encoder,
            "hw_accelerated": self._hw_accelerated,
            "v4l2_m2m_available": self._v4l2_m2m_available,
            "stream_name": self.stream_name if self.available else "",
            "h264_stream_name": H264_STREAM_NAME,
            "low_bandwidth_bitrate": settings.low_bandwidth_bitrate,
        }


transcode_service = TranscodeService()