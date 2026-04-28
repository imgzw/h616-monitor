from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000

    camera_device: str = "/dev/video1"
    camera_name: str = "camera_h264"

    recordings_dir: Path = Path("/opt/h616-monitor/recordings")
    segment_duration: int = 300
    recording_format: str = "mp4"

    disk_high_threshold: float = 0.80
    disk_low_threshold: float = 0.70
    cleanup_interval: int = 300

    go2rtc_host: str = "127.0.0.1"
    go2rtc_port: int = 1984

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    v4l2_ctl_path: str = "v4l2-ctl"

    thumbnail_width: int = 320
    thumbnail_height: int = 180

    thermal_zone_path: str = "/sys/class/thermal/thermal_zone0/temp"
    temp_high_threshold: float = 75.0
    temp_critical_threshold: float = 85.0

    low_bandwidth_bitrate: int = 1500
    low_bandwidth_stream_name: str = "camera_low"

    cors_origins: list[str] = ["*"]

    model_config = {"env_prefix": "H616_", "env_file": ".env", "extra": "ignore"}


settings = Settings()