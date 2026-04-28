import asyncio
import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)


class CameraControlService:
    """Controls V4L2 camera parameters (zoom, brightness, contrast, etc.)."""

    def __init__(self):
        self._device = settings.camera_device
        self._controls_cache: list[dict] | None = None
        self._controls_ts: float = 0.0
        self._cache_ttl: float = 5.0

    async def get_info(self) -> dict:
        cmd = [settings.v4l2_ctl_path, "--device", self._device, "--info"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        info: dict = {}
        for line in stdout.decode(errors="replace").splitlines():
            line = line.strip()
            if line.startswith("Card type"):
                info["card"] = line.split(":", 1)[1].strip()
            elif line.startswith("Driver name"):
                info["driver"] = line.split(":", 1)[1].strip()
            elif line.startswith("Bus info"):
                info["bus_info"] = line.split(":", 1)[1].strip()
        info["device"] = self._device
        return info

    async def get_resolution(self) -> str:
        """Get current video resolution from V4L2."""
        cmd = [
            settings.v4l2_ctl_path,
            "--device", self._device,
            "--get-fmt-video",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return ""
        output = stdout.decode(errors="replace")
        # Parse: "Width/Height      : 1920/1080"
        for line in output.splitlines():
            line = line.strip()
            if "Width/Height" in line or "width" in line.lower() and "height" in line.lower():
                parts = line.split(":")
                if len(parts) >= 2:
                    res = parts[1].strip()
                    # Normalize "1920/1080" → "1920x1080"
                    return res.replace("/", "x")
        return ""

    async def get_formats(self) -> list[str]:
        """List supported pixel formats from V4L2."""
        cmd = [
            settings.v4l2_ctl_path,
            "--device", self._device,
            "--list-formats",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []
        formats: list[str] = []
        for line in stdout.decode(errors="replace").splitlines():
            line = line.strip()
            # Parse lines like: [0]: 'YUYV' (YUYV 4:2:2)
            if line.startswith("["):
                try:
                    start = line.index("'") + 1
                    end = line.index("'", start)
                    formats.append(line[start:end])
                except ValueError:
                    continue
        return formats

    async def list_controls(self) -> list[dict]:
        """List V4L2 controls with TTL cache to avoid repeated process spawns."""
        now = time.monotonic()
        if self._controls_cache is not None and (now - self._controls_ts) < self._cache_ttl:
            return self._controls_cache

        cmd = [
            settings.v4l2_ctl_path,
            "--device", self._device,
            "--list-ctrls",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        result = self._parse_controls(stdout.decode(errors="replace"))
        self._controls_cache = result
        self._controls_ts = now
        return result

    def invalidate_cache(self) -> None:
        """Force refresh of controls cache on next list_controls() call."""
        self._controls_cache = None
        self._controls_ts = 0.0

    async def get_control(self, name: str) -> dict | None:
        cmd = [
            settings.v4l2_ctl_path,
            "--device", self._device,
            "--get-ctrl", name,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return None
        value = stdout.decode(errors="replace").strip()
        controls = await self.list_controls()
        for ctrl in controls:
            if ctrl["name"] == name:
                try:
                    ctrl["current_val"] = int(value)
                except ValueError:
                    pass
                return ctrl
        return None

    async def set_control(self, name: str, value: int) -> bool:
        cmd = [
            settings.v4l2_ctl_path,
            "--device", self._device,
            "--set-ctrl", f"{name}={value}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode != 0:
            logger.error("Failed to set %s=%d", name, value)
            return False
        logger.info("Set %s=%d", name, value)
        self.invalidate_cache()
        return True

    async def zoom_in(self, step: int = 1) -> int | None:
        ctrl = await self.get_control("zoom_absolute")
        if not ctrl:
            ctrl = await self.get_control("zoom_relative")
        if not ctrl:
            return None
        new_val = min(ctrl["current_val"] + step, ctrl["max_val"])
        name = ctrl["name"]
        if await self.set_control(name, new_val):
            return new_val
        return None

    async def zoom_out(self, step: int = 1) -> int | None:
        ctrl = await self.get_control("zoom_absolute")
        if not ctrl:
            ctrl = await self.get_control("zoom_relative")
        if not ctrl:
            return None
        new_val = max(ctrl["current_val"] - step, ctrl["min_val"])
        name = ctrl["name"]
        if await self.set_control(name, new_val):
            return new_val
        return None

    async def zoom_set(self, value: int) -> int | None:
        for name in ("zoom_absolute", "zoom_relative"):
            ctrl = await self.get_control(name)
            if ctrl:
                clamped = max(ctrl["min_val"], min(value, ctrl["max_val"]))
                if await self.set_control(name, clamped):
                    return clamped
        return None

    def _parse_controls(self, raw: str) -> list[dict]:
        controls = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                name_part, rest = line.split(" ", 1)
                name = name_part.strip()
                if name.startswith("0x") or name.isdigit():
                    continue
                props = {}
                for token in rest.split():
                    if "=" in token:
                        k, v = token.split("=", 1)
                        props[k] = v
                if "min" not in props:
                    continue
                ctrl = {
                    "name": name,
                    "type": props.get("type", "int"),
                    "min_val": int(props.get("min", 0)),
                    "max_val": int(props.get("max", 0)),
                    "step": int(props.get("step", 1)),
                    "default_val": int(props.get("default", 0)),
                    "current_val": int(props.get("value", 0)),
                }
                controls.append(ctrl)
            except (ValueError, KeyError):
                continue
        return controls


camera_control = CameraControlService()