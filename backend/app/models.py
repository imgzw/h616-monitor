from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CameraControl(BaseModel):
    name: str
    type: str
    min_val: int
    max_val: int
    step: int
    default_val: int
    current_val: int
    menu_items: Optional[dict[int, str]] = None


class CameraInfo(BaseModel):
    device: str
    card: str
    driver: str
    bus_info: str
    resolution: str
    formats: list[str]


class SetControlRequest(BaseModel):
    value: int


class RecordingStatus(BaseModel):
    is_recording: bool
    started_at: Optional[datetime] = None
    segment_duration: int
    pid: Optional[int] = None


class RecordingItem(BaseModel):
    filename: str
    path: str
    size_bytes: int
    size_human: str
    created_at: datetime
    duration: Optional[float] = None
    thumbnail: Optional[str] = None


class RecordingList(BaseModel):
    items: list[RecordingItem]
    total: int
    page: int
    page_size: int


class StorageInfo(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    usage_percent: float
    recordings_bytes: int
    recordings_count: int


class CPUTempInfo(BaseModel):
    temp_c: float
    high_threshold: float
    critical_threshold: float
    warning: bool


class TranscodeInfo(BaseModel):
    available: bool
    encoder: str
    hw_accelerated: bool
    v4l2_m2m_available: bool
    stream_name: str
    low_bandwidth_bitrate: int


class SystemStatus(BaseModel):
    stream_active: bool
    recording: RecordingStatus
    storage: StorageInfo
    cpu_temp: CPUTempInfo
    transcode: TranscodeInfo
    uptime_seconds: float