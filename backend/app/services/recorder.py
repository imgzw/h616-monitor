import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class RecorderService:
    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._started_at: datetime | None = None
        self._recording_dir: Path | None = None
        self._lock = asyncio.Lock()
        self._auto_restart = True

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process and self.is_recording else None

    async def start(self) -> bool:
        async with self._lock:
            if self.is_recording:
                logger.warning("Recording already in progress")
                return False

            now = datetime.now()
            self._recording_dir = settings.recordings_dir / now.strftime("%Y-%m-%d")
            self._recording_dir.mkdir(parents=True, exist_ok=True)
            self._started_at = now
            self._auto_restart = True

            stream_url = (
                f"http://{settings.go2rtc_host}:{settings.go2rtc_port}"
                f"/api/stream.{settings.recording_stream_format}?src={settings.recording_stream_name}"
            )

            output_pattern = str(self._recording_dir / "%H-%M-%S.mp4")

            cmd = [
                settings.ffmpeg_path,
                "-hide_banner",
                "-loglevel", "warning",
                "-i", stream_url,
                "-an",
            ]

            if settings.recording_video_codec == "copy":
                cmd.extend(["-c:v", "copy"])
            else:
                cmd.extend([
                    "-threads", "2",
                    "-c:v", settings.recording_video_codec,
                    "-preset", settings.recording_preset,
                    "-tune", "zerolatency",
                    "-crf", str(settings.recording_crf),
                    "-pix_fmt", "yuv420p",
                ])

            cmd.extend([
                "-f", "segment",
                "-segment_time", str(settings.segment_duration),
                "-segment_format", settings.recording_format,
                "-segment_format_options", "movflags=+faststart",
                "-strftime", "1",
                "-reset_timestamps", "1",
                "-segment_atclocktime", "1",
                output_pattern,
            ])

            logger.info("Starting recording: %s", " ".join(cmd))

            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp,
                )
                await asyncio.sleep(1)
                rc = self._process.poll()
                if rc is not None:
                    logger.error("ffmpeg exited during startup (rc=%d)", rc)
                    self._process = None
                    self._started_at = None
                    return False
                asyncio.create_task(self._monitor_process())
                logger.info("Recording started, PID=%d", self._process.pid)
                return True
            except Exception:
                logger.exception("Failed to start recording")
                self._process = None
                self._started_at = None
                return False

    async def stop(self) -> bool:
        async with self._lock:
            if not self.is_recording:
                return False
            self._auto_restart = False
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            pid = self._process.pid
            self._process = None
            self._started_at = None
            logger.info("Recording stopped, PID=%d", pid)
            return True

    async def _monitor_process(self):
        while True:
            await asyncio.sleep(5)
            if self._process is None:
                return
            if not self._auto_restart:
                return
            rc = self._process.poll()
            if rc is not None:
                logger.error("ffmpeg exited unexpectedly (rc=%d), restarting...", rc)
                self._process = None
                self._started_at = None
                await asyncio.sleep(2)
                await self.start()

    async def get_duration(self, filepath: Path) -> float | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                settings.ffprobe_path,
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(filepath),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return float(stdout.strip())
        except Exception:
            return None


recorder = RecorderService()
