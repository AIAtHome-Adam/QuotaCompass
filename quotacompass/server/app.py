from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from quotacompass.core.advisor import advise
from quotacompass.core.config import AppConfig, load_config
from quotacompass.core.demo import demo_snapshot
from quotacompass.core.demo_history import demo_history
from quotacompass.core.models import StateSnapshot
from quotacompass.core.reauth import ReauthManager
from quotacompass.core.runtime import remove_pidfile, write_pidfile
from quotacompass.core.scheduler import PollingScheduler
from quotacompass.core.service import QuotaService
from quotacompass.server.schemas import ManualUpdate


def create_app(
    config: AppConfig | None = None,
    *,
    service: QuotaService | None = None,
    demo: bool = False,
) -> FastAPI:
    settings = config or load_config()
    quota_service = service or QuotaService(settings)
    reauth_manager = ReauthManager(settings, quota_service.state_dir)

    scheduler = PollingScheduler(
        quota_service.poll,
        interval_seconds=settings.poll.default_interval_minutes * 60,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        write_pidfile(quota_service.state_dir, settings.server.host, settings.server.port)
        if not demo and quota_service.adapters:
            scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()
            remove_pidfile(quota_service.state_dir)

    app = FastAPI(title="QuotaCompass", version="0.1.0", lifespan=lifespan)
    app.state.config = settings
    app.state.service = quota_service
    app.state.demo = demo
    app.state.scheduler = scheduler
    app.state.reauth_manager = reauth_manager

    def token_matches(authorization: str | None, token: str | None) -> bool:
        if not authorization or not token:
            return False
        return compare_digest(authorization, f"Bearer {token}")

    def authorize(authorization: str | None = Header(default=None)) -> None:
        token = settings.server.auth_token
        if not token:
            return
        if not token_matches(authorization, token):
            raise HTTPException(status_code=401, detail="Invalid bearer token")

    def authorize_reauth(request: Request, authorization: str | None = Header(default=None)) -> str:
        mode = settings.security.reauth_trigger
        if mode == "off":
            raise HTTPException(status_code=403, detail="Reauthentication is disabled")
        host = request.client.host if request.client else "unknown"
        if host in {"127.0.0.1", "::1", "testclient"}:
            return "loopback"
        if mode != "remote":
            raise HTTPException(status_code=403, detail="Remote reauthentication is disabled")
        if not token_matches(authorization, settings.security.reauth_token):
            raise HTTPException(status_code=401, detail="Separate reauthentication token required")
        return host

    def snapshot() -> StateSnapshot:
        if app.state.demo:
            return demo_snapshot()
        current = quota_service.current()
        if current is None:
            raise HTTPException(status_code=503, detail="No quota snapshot is available yet")
        return current

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "demo" if app.state.demo else "live"}

    @app.get("/api/v1/status", dependencies=[Depends(authorize)])
    def status() -> StateSnapshot:
        return snapshot()

    @app.get("/api/v1/suggest", dependencies=[Depends(authorize)])
    def suggest(task: str | None = Query(default=None)) -> dict[str, object]:
        current = snapshot()
        return advise(current.providers, settings.advisor, task=task).model_dump(mode="json")

    @app.get("/api/v1/nudges", dependencies=[Depends(authorize)])
    def nudges() -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in snapshot().advisor.expiring_unused]

    @app.get("/api/v1/providers/{provider_id}/history", dependencies=[Depends(authorize)])
    def history(
        provider_id: str,
        days: int = Query(default=30, ge=1, le=365),
        window: str | None = Query(default=None),
    ) -> list[dict]:
        items = (
            demo_history(provider_id, days)
            if app.state.demo
            else quota_service.history(provider_id, days)
        )
        if window:
            for item in items:
                item.windows = [
                    value
                    for value in item.windows
                    if value.window_id == window or value.name == window
                ]
        return [item.model_dump(mode="json") for item in items]

    @app.post("/api/v1/providers/{provider_id}/manual", dependencies=[Depends(authorize)])
    async def update_manual(provider_id: str, update: ManualUpdate) -> StateSnapshot:
        try:
            return await quota_service.set_manual(provider_id, update.windows)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/poll", dependencies=[Depends(authorize)])
    async def poll() -> StateSnapshot:
        if app.state.demo:
            return demo_snapshot()
        return await quota_service.poll()

    @app.post("/api/v1/providers/{provider_id}/reauth")
    def reauth(provider_id: str, origin: str = Depends(authorize_reauth)) -> dict[str, str | int]:
        try:
            return reauth_manager.start(provider_id, origin=origin)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    static_dir = Path(__file__).with_name("static")
    if static_dir.exists():
        assets = static_dir / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/", include_in_schema=False)
        def dashboard() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    @app.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "font-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return app


app = create_app()
