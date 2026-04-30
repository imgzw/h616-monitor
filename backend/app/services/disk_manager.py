import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class DiskManagerService:
    """Monitors disk usage and automatically cleans up old recordings."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._refresh_task: asyncio.Task | None = None
        self._file_index: dict[str, dict[str, float]] = {}
        self._recordings_size: int = 0

    def start(self):
        self._rebuild_index()
        self._task = asyncio.create_task(self._cleanup_loop())
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info(
            "Disk cleanup task started (interval=%ds, high=%.0f%%, low=%.0f%%)",
            settings.cleanup_interval,
            settings.disk_high_threshold * 100,
            settings.disk_low_threshold * 100,
        )

    def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()

    def _rebuild_index(self):
        rec_dir = settings.recordings_dir
        rec_dir.mkdir(parents=True, exist_ok=True)
        self._file_index = {}
        self._recordings_size = 0
        for f in rec_dir.rglob("*.mp4"):
            if f.is_file():
                st = f.stat()
                rel = str(f.relative_to(rec_dir))
                self._file_index[rel] = {"mtime": st.st_mtime, "size": st.st_size}
                self._recordings_size += st.st_size
        logger.info("File index rebuilt: %d recordings, %s total",
                     len(self._file_index), self._human_size(self._recordings_size))

    def _index_add(self, rel_path: str):
        filepath = settings.recordings_dir / rel_path
        if filepath.is_file():
            st = filepath.stat()
            self._file_index[rel_path] = {"mtime": st.st_mtime, "size": st.st_size}
            self._recordings_size += st.st_size

    def _index_remove(self, rel_path: str):
        entry = self._file_index.pop(rel_path, None)
        if entry:
            self._recordings_size -= entry["size"]

    async def get_storage_info(self) -> dict:
        rec_dir = settings.recordings_dir
        rec_dir.mkdir(parents=True, exist_ok=True)

        disk = shutil.disk_usage(str(rec_dir))
        return {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "usage_percent": round(disk.used / disk.total * 100, 1),
            "recordings_bytes": self._recordings_size,
            "recordings_count": len(self._file_index),
        }

    async def list_recordings(
        self, page: int = 1, page_size: int = 20, date_filter: str | None = None
    ) -> dict:
        rec_dir = settings.recordings_dir
        rec_dir.mkdir(parents=True, exist_ok=True)

        if date_filter:
            matching = {
                p: info for p, info in self._file_index.items()
                if p.startswith(date_filter + "/")
            }
        else:
            matching = dict(self._file_index)

        sorted_paths = sorted(matching.keys(), key=lambda p: matching[p]["mtime"], reverse=True)
        total = len(sorted_paths)
        start = (page - 1) * page_size
        end = start + page_size
        page_paths = sorted_paths[start:end]

        items = []
        for rel_path in page_paths:
            info = matching[rel_path]
            date_part = Path(rel_path).parts[0] if len(Path(rel_path).parts) > 1 else ""
            time_part = Path(rel_path).stem

            items.append({
                "filename": Path(rel_path).name,
                "path": rel_path,
                "size_bytes": info["size"],
                "size_human": self._human_size(info["size"]),
                "created_at": datetime.fromtimestamp(info["mtime"]),
                "duration": None,
                "thumbnail": f"/api/recordings/thumbnail/{rel_path}",
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def delete_recording(self, rel_path: str) -> bool:
        filepath = self._safe_recording_path(rel_path)
        if filepath is None:
            return False
        if not filepath.is_file():
            return False
        try:
            filepath.unlink()
            self._index_remove(rel_path)
            parent = filepath.parent
            if parent != settings.recordings_dir:
                try:
                    parent.rmdir()
                except OSError:
                    pass
            logger.info("Deleted recording: %s", rel_path)
            return True
        except Exception:
            logger.exception("Failed to delete %s", rel_path)
            return False

    async def delete_date_recordings(self, date_str: str) -> int:
        date_dir = settings.recordings_dir / date_str
        if not date_dir.is_dir():
            return 0
        count = 0
        for f in date_dir.glob("*.mp4"):
            try:
                rel = str(f.relative_to(settings.recordings_dir))
                f.unlink()
                self._index_remove(rel)
                count += 1
            except Exception:
                logger.exception("Failed to delete %s", f)
        try:
            date_dir.rmdir()
        except OSError:
            pass
        logger.info("Deleted %d recordings from %s", count, date_str)
        return count

    async def cleanup_if_needed(self) -> int:
        storage = await self.get_storage_info()
        usage = storage["usage_percent"] / 100.0

        if usage < settings.disk_high_threshold:
            return 0

        logger.warning(
            "Disk usage %.1f%% exceeds threshold %.0f%%, starting cleanup",
            usage * 100,
            settings.disk_high_threshold * 100,
        )

        deleted = 0
        date_dirs = sorted(
            (d for d in settings.recordings_dir.iterdir() if d.is_dir() and d.name.startswith("20") and d.name != ".thumbnails"),
            key=lambda d: d.name,
        )

        for date_dir in date_dirs:
            disk = shutil.disk_usage(str(settings.recordings_dir))
            current_usage = disk.used / disk.total
            if current_usage <= settings.disk_low_threshold:
                break

            count = await self.delete_date_recordings(date_dir.name)
            deleted += count

        logger.info("Cleanup complete, deleted %d files", deleted)
        return deleted

    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(settings.cleanup_interval)
                await self.cleanup_if_needed()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Disk cleanup loop error")

    async def _refresh_loop(self):
        while True:
            try:
                await asyncio.sleep(60)
                self._rebuild_index()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("File index refresh error")

    @staticmethod
    def _safe_recording_path(rel_path: str) -> Path | None:
        base = settings.recordings_dir.resolve()
        filepath = (base / rel_path).resolve()
        try:
            filepath.relative_to(base)
        except ValueError:
            return None
        return filepath

    @staticmethod
    def _human_size(num_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if num_bytes < 1024:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024
        return f"{num_bytes:.1f} PB"


disk_manager = DiskManagerService()
