from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Body, FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import paths
from .checker import Checker, Config


class ConfigIn(BaseModel):
    term: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    catalog_nbr: str = Field(min_length=1)
    seat_limit: int = Field(ge=1)
    interval: int = Field(ge=10)


def create_app(on_alert=None, on_quit=None) -> FastAPI:
    checker = Checker(on_alert=on_alert)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await checker.stop()

    app = FastAPI(lifespan=lifespan)
    app.state.checker = checker

    @app.middleware("http")
    async def log_posts(request, call_next):
        if request.method == "POST":  # audit trail: who triggers actions (shows up in app.log when frozen)
            print("POST", request.url.path, "ua=", request.headers.get("user-agent", "")[:60], flush=True)
        return await call_next(request)

    @app.get("/api/state")
    async def state():
        return checker.snapshot()

    @app.get("/api/catalog")
    async def catalog():
        import json

        try:
            return json.loads(paths.catalog_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"term": None, "schools": []}

    @app.post("/api/signin")
    async def signin(info: dict | None = Body(None)):
        print("signin click info:", info, flush=True)
        return {"ok": checker.sign_in()}

    @app.post("/api/start")
    async def start(cfg: ConfigIn):
        return {"ok": checker.start(Config(**cfg.model_dump()))}

    @app.post("/api/stop")
    async def stop():
        await checker.stop()
        return {"ok": True}

    @app.post("/api/app/test-alert")
    async def app_test_alert():
        fn = getattr(app.state, "test_alert", None)
        if fn:
            fn()
        return {"ok": bool(fn)}

    @app.post("/api/app/caesar")
    async def app_caesar():
        import webbrowser

        from .checker import URL

        webbrowser.open(URL)
        return {"ok": True}

    @app.post("/api/app/quit")
    async def app_quit():
        if on_quit:
            on_quit()
        return {"ok": True}

    static = paths.static_dir()
    if static.exists():
        app.mount("/", StaticFiles(directory=static, html=True), name="static")
    return app
