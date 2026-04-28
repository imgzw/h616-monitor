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
        self._file_index: dict[str, float] = {}

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
        for f in rec_dir.rglob("*.mp4"):
            if f.is_file():
                self._file_index[str(f.relative_to(rec_dir))] = f.stat().st_mtime
        logger.info("File index rebuilt: %d recordings", len(self._file_index))

    def _index_add(self, rel_path: str):
        filepath = settings.recordings_dir / rel_path
        if filepath.is_file():
            self._file_index[rel_path] = filepath.stat().st_mtime

    def _index_remove(self, rel_path: str):
        self._file_index.pop(rel_path, None)

    async def get_storage_info(self) -> dict:
        rec_dir = settings.recordings_dir
        rec_dir.mkdir(parents=True, exist_ok=True)

        disk = shutil.disk_usage(str(rec_dir))
        rec_size = sum(
            (settings.recordings_dir / p).stat().st_size
            for p in self._file_index
            if (settings.recordings_dir / p).is_file()
        )
        rec_count = len(self._file_index)

        return {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "usage_percent": round(disk.used / disk.total * 100, 1),
            "recordings_bytes": rec_size,
            "recordings_count": rec_count,
        }

    async def list_recordings(
        self, page: int = 1, page_size: int = 20, date_filter: str | None = None
    ) -> dict:
        rec_dir = settings.recordings_dir
        rec_dir.mkdir(parents=True, exist_ok=True)

        if date_filter:
            matching = {
                p: mtime for p, mtime in self._file_index.items()
                if p.startswith(date_filter + "/")
            }
        else:
            matching = dict(self._file_index)

        sorted_paths = sorted(matching.keys(), key=lambda p: matching[p], reverse=True)
        total = len(sorted_paths)
        start = (page - 1) * page_size
        end = start + page_size
        page_paths = sorted_paths[start:end]

        items = []
        for rel_path in page_paths:
            filepath = rec_dir / rel_path
            if not filepath.is_file():
                continue
            stat = filepath.stat()
            date_part = Path(rel_path).parts[0] if len(Path(rel_path).parts) > 1 else ""
            time_part = Path(rel_path).stem

            items.append({
                "filename": filepath.name,
                "path": rel_path,
                "size_bytes": stat.st_size,
                "size_human": self._human_size(stat.st_size),
                "created_at": datetime.fromtimestamp(stat.st_mtime),
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
        filepath = settings.recordings_dir / rel_path
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
            current_usage = (await self.get_storage_info())["usage_percent"] / 100.0
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
    def _human_size(num_bytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if num_bytes < 1024:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024
        return f"{num_bytes:.1f} PB"


disk_manager = DiskManagerService()