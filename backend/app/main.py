from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.registry import discover_modules

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.maintenance_condition = asyncio.Condition()
    app.state.maintenance = False
    app.state.active_requests = 0
    async def ticks():
        while True:
            await asyncio.sleep(30)
            for module in app.state.modules:
                if module.background_tick:
                    try:
                        async with app.state.maintenance_condition:
                            await app.state.maintenance_condition.wait_for(lambda: app.state.active_requests == 0)
                            app.state.maintenance = True
                        try:
                            await asyncio.to_thread(module.background_tick)
                        finally:
                            async with app.state.maintenance_condition:
                                app.state.maintenance = False
                                app.state.maintenance_condition.notify_all()
                    except Exception:
                        logging.getLogger(__name__).exception("Module background task failed: %s", module.name)
    task = asyncio.create_task(ticks())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Anti-Rot", version="1.0.0", lifespan=lifespan)
app.state.modules = discover_modules()
for module in app.state.modules:
    app.include_router(module.router, prefix="/api")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # One-worker deployment: keep snapshots consistent with media references and DB writes.
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        async with app.state.maintenance_condition:
            await app.state.maintenance_condition.wait_for(lambda: not app.state.maintenance)
            app.state.active_requests += 1
        try:
            response = await call_next(request)
        finally:
            async with app.state.maintenance_condition:
                app.state.active_requests -= 1
                app.state.maintenance_condition.notify_all()
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class HealthOut(BaseModel):
    status: str


@app.get("/api/health", response_model=HealthOut)
def health() -> dict:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


static: Path = get_settings().static_dir.resolve()
if static.is_dir():
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", response_class=FileResponse)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        target = (static / path).resolve()
        if target.is_relative_to(static) and target.is_file():
            return FileResponse(target, headers={"Cache-Control": "no-cache"})
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})
