# H616 Monitor Platform — Agent Guide

## What This Is

Embedded surveillance platform for Allwinner H616 (Armbian). USB camera → go2rtc (WebRTC/MJPEG streaming) → browser preview + ffmpeg segmented recording + V4L2 zoom control. Dark-themed Vue 3 dashboard.

## Architecture

```
USB Camera → go2rtc (streams: camera, camera_h264)
                  ├→ Browser live preview (<500ms WebRTC)
                  ├→ ffmpeg MJPEG→MP4 segmented recording (5-min slices)
                  └→ V4L2 zoom/control

nginx:80 → /api/ws, /api/webrtc, /api/stream → go2rtc:1984
         → /api/*                           → FastAPI:8000
         → /*                              → Vue SPA static files
```

## Commands

```bash
# Frontend dev
cd frontend && npm ci && npm run dev          # Vite dev server on :5173, proxies /api → :8000

# Frontend production build
cd frontend && npm run build                  # vue-tsc + vite build → frontend/dist/

# Backend dev
cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1   # or: bash run.sh

# Full deployment on H616 device
sudo bash deploy/install.sh                  # idempotent; --force to reinstall/rebuild
```

- **No test runner configured** in either frontend or backend. No test files exist.
- **No linter/formatter config** found. No eslint, prettier, ruff, or black.
- `npm run build` runs `vue-tsc` typecheck before vite build — type errors will block the build.

## Project Structure

```
h616/
├── backend/                  # Python FastAPI
│   ├── app/
│   │   ├── main.py          # FastAPI app, lifespan, CORS, static mount
│   │   ├── config.py        # pydantic-settings, all env vars with H616_ prefix
│   │   ├── models.py        # Pydantic response models
│   │   ├── routers/
│   │   │   ├── camera.py    # /api/camera/* — info, controls, zoom, stream URLs
│   │   │   ├── recordings.py # /api/recordings/* — start/stop/list/download/thumbnail
│   │   │   └── system.py    # /api/status, /api/storage, /api/temp, /api/cleanup, /api/go2rtc-config
│   │   └── services/
│   │       ├── camera_control.py   # V4L2 subprocess wrapper (v4l2-ctl), TTL cache
│   │       ├── disk_manager.py     # Disk monitor, auto-cleanup old recordings
│   │       ├── recorder.py         # ffmpeg subprocess manager, auto-restart on crash
│   │       ├── stream_service.py   # go2rtc HTTP client, stream URL builder
│   │       └── transcode_service.py # H.264 encoder detection (V4L2 M2M vs libx264)
│   ├── requirements.txt     # fastapi, uvicorn, pydantic-settings, httpx, python-multipart
│   └── run.sh               # Dev launcher with env defaults + uvicorn
├── frontend/                 # Vue 3 + TypeScript + Vite + Element Plus
│   ├── src/
│   │   ├── api/index.ts     # Axios client, all API calls + TypeScript interfaces
│   │   ├── App.vue          # Main layout, sidebar nav, status polling every 10s
│   │   ├── router/index.ts  # / → LiveView, /recordings → RecordingsView
│   │   ├── views/
│   │   │   ├── LiveView.vue
│   │   │   └── RecordingsView.vue
│   │   ├── components/
│   │   │   ├── VideoPlayer.vue
│   │   │   ├── ZoomControl.vue
│   │   │   └── RecordingCard.vue
│   │   └── styles/main.css  # Dark theme CSS vars (--bg-primary, --accent, etc.)
│   ├── vite.config.ts        # Proxy /api → localhost:8000
│   └── tsconfig.json         # strict mode, @/* path alias
├── config/
│   └── go2rtc.yaml           # Stream definitions (camera: v4l2 mjpeg, camera_h264: exec ffmpeg)
├── deploy/
│   ├── install.sh            # One-shot idempotent installer (system deps, go2rtc, venv, systemd, nginx)
│   ├── nginx.conf            # Reverse proxy: /api/ws → go2rtc WS, /api/webrtc|stream → go2rtc, /api → FastAPI
│   ├── go2rtc.service        # systemd: go2rtc binary, 256M mem limit
│   └── h616-monitor.service  # systemd: uvicorn in venv, DeviceAllow=/dev/video1, 256M mem limit
└── recordings/               # MP4 output dir (date-segmented: YYYY-MM-DD/HH-MM-SS.mp4)
```

## Key Conventions & Gotchas

### Backend

- **Env prefix**: All env vars use `H616_` prefix (e.g., `H616_CAMERA_DEVICE`, `H616_GO2RTC_PORT`). Defined in `config.py` via `pydantic-settings`.
- **Singleton services**: Each service module exports a module-level instance (`recorder`, `disk_manager`, `camera_control`, `stream_service`, `transcode_service`). Do not instantiate classes directly.
- **Process management**: `recorder.py` uses `subprocess.Popen` for ffmpeg, with async `_monitor_process()` that auto-restarts on crash. Uses `os.setpgrp` for process group isolation.
- **Camera device default**: `/dev/video1` (not `video0`). README says `video0` but config.py defaults to `video1`. The systemd service allows `DeviceAllow=/dev/video1`.
- **go2rtc stream names**: `camera` (MJPEG raw) and `camera_h264` (libx264 transcoded). These are referenced by `settings.camera_name` which defaults to `camera_h264`.
- **Thumbnail generation**: Uses ffmpeg subprocess with 10s timeout. Thumbnails stored in `recordings_dir/.thumbnails/`.
- **Disk cleanup**: Background task every 5 min (`settings.cleanup_interval=300`). Deletes oldest day's recordings when usage exceeds `disk_high_threshold` (80%), down to `disk_low_threshold` (70%).
- **File index**: `disk_manager` maintains an in-memory `_file_index` dict, rebuilt every 60s via `_refresh_loop()`.
- **CORS**: Wide open (`allow_origins=["*"]`). Fine for LAN-only device.
- **Lifespan**: On startup: create recordings dir, start disk_manager, initialize transcode_service. On shutdown: stop disk_manager, stop recorder if active.
- **Frontend static files**: FastAPI mounts `frontend/dist/` at `/` in dev. Production uses nginx.

### Frontend

- **Path alias**: `@/*` → `./src/*` (configured in tsconfig, NOT in vite.config — so `@/` imports work in TS but Vite resolves via tsconfig).
- **Dark theme**: Uses CSS custom properties in `main.css`. Element Plus dark mode via `html.dark` class overrides.
- **No state management library**: Uses Vue `reactive()` in App.vue for global status, axios direct calls in api/index.ts.
- **Status polling**: App.vue polls `/api/status` every 10 seconds.
- **Build order**: `vue-tsc` runs first (typecheck), then `vite build`. Type errors block the production build.
- **Language**: Chinese (zh-CN) — locale set in `index.html`, UI strings are in Chinese.

### Deployment

- **Target platform**: ARM64 (Allwinner H616 running Armbian). go2rtc binary is `go2rtc_linux_arm64`.
- **install.sh is idempotent**: Skips already-installed deps unless `--force`. Uses md5 hash of `package.json` + `App.vue` to skip frontend rebuild.
- **Service user**: `h616-monitor` (created by install script, added to `video` group).
- **Install directory**: `/opt/h616-monitor/` (backend, frontend/dist, config, recordings).
- **Service start order**: go2rtc first → h616-monitor → nginx.
- **nginx routes**: `/api/ws` and `/api/webrtc` and `/api/stream` proxy to go2rtc:1984 (with WebSocket upgrade and buffering disabled). `/api/` proxies to FastAPI:8000. `/` serves Vue SPA with `try_files` fallback.
- **Memory limits**: Both go2rtc and h616-monitor services capped at 256M RAM, 50% CPU.

### Config / Environment

| Variable | Default | Purpose |
|---|---|---|
| `H616_CAMERA_DEVICE` | `/dev/video1` | V4L2 device path |
| `H616_CAMERA_NAME` | `camera_h264` | go2rtc stream name |
| `H616_RECORDING_STREAM_NAME` | `camera_h264` | go2rtc H.264 stream used as ffmpeg recording input |
| `H616_RECORDING_STREAM_FORMAT` | `ts` | go2rtc `/api/stream.{format}` input for recording; TS carries H.264 reliably |
| `H616_RECORDINGS_DIR` | `/opt/h616-monitor/recordings` | MP4 storage |
| `H616_SEGMENT_DURATION` | `300` | Seconds per MP4 segment |
| `H616_RECORDING_VIDEO_CODEC` | `copy` | Avoids extra CPU by remuxing go2rtc H.264 into MP4 segments |
| `H616_RECORDING_PRESET` | `ultrafast` | ffmpeg encoder preset for recordings |
| `H616_RECORDING_CRF` | `23` | H.264 quality/size setting for recordings |
| `H616_DISK_HIGH_THRESHOLD` | `0.80` | Trigger cleanup |
| `H616_DISK_LOW_THRESHOLD` | `0.70` | Cleanup target |
| `H616_GO2RTC_HOST` | `127.0.0.1` | go2rtc address |
| `H616_GO2RTC_PORT` | `1984` | go2rtc port |
| `H616_HOST` | `0.0.0.0` | FastAPI bind host |
| `H616_PORT` | `8000` | FastAPI bind port |
| `H616_LOW_BANDWIDTH_BITRATE` | `1500` | Low-bitrate stream kbps |

- Backend `.env` file is read from `backend/.env` (via pydantic-settings `env_file=".env"` and systemd `EnvironmentFile`).

### API Quick Reference

All routes prefixed with `/api`:
- **System**: `GET /status`, `GET /storage`, `GET /temp`, `GET /transcode`, `GET /go2rtc-config`, `POST /cleanup`
- **Camera**: `GET /camera/info`, `GET /camera/controls`, `GET|PUT /camera/control/{name}`, `POST /camera/zoom/in|out|set`, `GET /camera/stream-url`, `GET /camera/low-bandwidth-url`
- **Recordings**: `POST /recordings/start|stop`, `GET /recordings/status`, `GET /recordings?page=&page_size=&date=`, `DELETE /recordings/{path}`, `GET /recordings/download/{path}`, `GET /recordings/thumbnail/{path}`

### What Not To Do

- Don't change `--workers 1` — the recorder and disk_manager use in-process state; multiple workers would break things.
- Don't add `as any` or `@ts-ignore` — `vue-tsc` strict mode is enforced in the build.
- Don't assume `/dev/video0` — the default device is `/dev/video1` (config.py, systemd service).
- Don't put tests inside `backend/app/` — there's no test infrastructure set up yet. Add a `backend/tests/` directory with pytest if adding tests.
- Don't run `uvicorn --workers > 1` — singleton services (`recorder`, `disk_manager`) are process-scoped.
