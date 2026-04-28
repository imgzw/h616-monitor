import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.routers import camera, recordings, system
from app.services.disk_manager import disk_manager
from app.services.recorder import recorder
from app.services.transcode_service import transcode_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.recordings_dir.mkdir(parents=True, exist_ok=True)
    disk_manager.start()
    await transcode_service.initialize()
    logger.info("H616 Monitor Platform started (transcode: %s)", transcode_service.encoder or "N/A")
    yield
    disk_manager.stop()
    if recorder.is_recording:
        await recorder.stop()
    logger.info("H616 Monitor Platform stopped")


app = FastAPI(title="H616 Monitor", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(camera.router)
app.include_router(recordings.router)
app.include_router(system.router)

frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dist), html=True),
        name="frontend",
    )