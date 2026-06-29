"""허브 FastAPI 앱 — 라우터 등록 + 정적 SPA 서빙."""
import os
import threading
import time

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .routers import foreign, intake, pipeline, registry, status, tools

app = FastAPI(title="LawQuery 허브", docs_url="/api/docs")
app.include_router(intake.router)
app.include_router(pipeline.router)
app.include_router(tools.router)
app.include_router(status.router)
app.include_router(registry.router)
app.include_router(foreign.router)

app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(config.STATIC_DIR, "index.html"))


@app.post("/api/shutdown")
def shutdown():
    """UI '허브 종료' — 잠깐 뒤 프로세스 종료(.pyw 는 콘솔이 없어 이 경로로 끔)."""
    def _kill():
        time.sleep(0.3)
        os._exit(0)
    threading.Thread(target=_kill, daemon=True).start()
    return {"ok": True}
