import asyncio
import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)


class CameraControlService:
    """V4L2 camera parameter control with TTL cache."""

    def __init__(self):
        self._device = settings.camera_device
        self._controls_cache: list[dict] | None = None
        self._controls_ts: float = 0.0
        self._cache_ttl: float = 5.0

    async def _run_v4l2(self, *args: str) -> tuple[str, str, int]:
        cmd = [settings.v4l2_ctl_path, "--device", self._device, *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return stdout.decode(errors="replace"), stderr.decode(errors="replace"), proc.returncode or 0
        except Exception:
            logger.exception("v4l2-ctl failed")
            return "", "", 1

    async def get_info(self) -> dict:
        stdout, stderr, rc = await self._run_v4l2("--info")
        info: dict = {}
        combined = stdout + "\n" + stderr
        for line in combined.splitlines():
            line = line.strip()
            if line.startswith("Card type"):
                info["card"] = line.split(":", 1)[1].strip()
            elif line.startswith("Driver name"):
                info["driver"] = line.split(":", 1)[1].strip()
            elif line.startswith("Bus info"):
                info["bus_info"] = line.split(":", 1)[1].strip()
        info["device"] = self._device
        if rc != 0:
            logger.warning("v4l2-ctl --info returned rc=%d: %s", rc, stderr.strip()[:200])
        return info

    async def get_resolution(self) -> str:
        stdout, stderr, rc = await self._run_v4l2("--get-fmt-video")
        if rc != 0:
            return ""
        combined = stdout + "\n" + stderr
        for line in combined.splitlines():
            line = line.strip()
            if "Width/Height" in line or ("width" in line.lower() and "height" in line.lower()):
                parts = line.split(":")
                if len(parts) >= 2:
                    res = parts[1].strip().replace("/", "x")
                    return res
        return ""

    async def get_formats(self) -> list[str]:
        stdout, stderr, rc = await self._run_v4l2("--list-formats")
        if rc != 0:
            return []
        combined = stdout + "\n" + stderr
        formats: list[str] = []
        for line in combined.splitlines():
            line = line.strip()
            if line.startswith("["):
                try:
                    start = line.index("'") + 1
                    end = line.index("'", start)
                    formats.append(line[start:end])
                except ValueError:
                    continue
        return formats

    async def list_controls(self) -> list[dict]:
        now = time.monotonic()
        if self._controls_cache is not None and (now - self._controls_ts) < self._cache_ttl:
            return self._controls_cache

        stdout, stderr, rc = await self._run_v4l2("--list-ctrls")
        combined = stdout + "\n" + stderr
        if rc != 0:
            logger.warning("v4l2-ctl --list-ctrls returned rc=%d: %s", rc, stderr.strip()[:200])
        result = self._parse_controls(combined)
        self._controls_cache = result
        self._controls_ts = now
        return result

    def invalidate_cache(self) -> None:
        self._controls_cache = None
        self._controls_ts = 0.0

    async def get_control(self, name: str) -> dict | None:
        stdout, stderr, rc = await self._run_v4l2("--get-ctrl", name)
        if rc != 0:
            return None
        value = stdout.strip() or stderr.strip()
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
        stdout, stderr, rc = await self._run_v4l2("--set-ctrl", f"{name}={value}")
        if rc != 0:
            logger.error("Failed to set %s=%d: %s", name, value, stderr.strip()[:200])
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