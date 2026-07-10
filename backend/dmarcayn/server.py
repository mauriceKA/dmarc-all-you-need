"""FastAPI application: JSON API under /api, static frontend for the rest."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Config
from .db import Database
from .poller import Poller

# repo layout: backend/dmarcayn/server.py -> <repo>/frontend/dist
_DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

_MAX_PAGE_SIZE = 200


def create_app(config: Config, db: Database, poller: Poller | None = None) -> FastAPI:
    app = FastAPI(title="dmarc-all-you-need", docs_url=None, redoc_url=None, openapi_url=None)
    api = APIRouter(prefix="/api")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # ------------------------------------------------------------- data

    @api.get("/domains")
    def domains():
        return db.domains()

    @api.get("/summary")
    def summary(domain: str, from_: int = Query(alias="from"), to: int = Query()):
        return db.summary(domain, from_, to)

    @api.get("/timeseries")
    def timeseries(
        domain: str,
        from_: int = Query(alias="from"),
        to: int = Query(),
        interval: str = "day",
    ):
        try:
            return db.timeseries(domain, from_, to, interval)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/alignment")
    def alignment(domain: str, from_: int = Query(alias="from"), to: int = Query()):
        return db.alignment(domain, from_, to)

    @api.get("/sources")
    def sources(
        domain: str,
        from_: int = Query(alias="from"),
        to: int = Query(),
        limit: int = Query(default=25, ge=1, le=_MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
    ):
        return db.sources(domain, from_, to, limit, offset)

    @api.get("/reports")
    def reports(
        domain: str,
        from_: int = Query(alias="from"),
        to: int = Query(),
        limit: int = Query(default=50, ge=1, le=_MAX_PAGE_SIZE),
        offset: int = Query(default=0, ge=0),
    ):
        return db.reports(domain, from_, to, limit, offset)

    @api.get("/reports/{report_id}")
    def report_detail(report_id: int):
        detail = db.report_detail(report_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="report not found")
        return detail

    # ------------------------------------------------------------- sync

    @api.post("/sync")
    def trigger_sync():
        if poller is None:
            raise HTTPException(status_code=503, detail="sync is not available")
        if not poller.trigger():
            return JSONResponse(status_code=409, content={"status": "already_running"})
        return JSONResponse(status_code=202, content={"status": "started"})

    @api.get("/sync/status")
    def sync_status():
        if poller is None:
            return {"running": False, "last_run_at": None, "last_result": None,
                    "last_error": None, "next_run_at": None}
        return poller.status.snapshot()

    app.include_router(api)

    # ---------------------------------------------------------- frontend

    static_dir = config.server.static_dir or _DEFAULT_STATIC_DIR
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    else:
        @app.get("/")
        def missing_frontend():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "frontend build not found",
                    "hint": f"run 'npm run build' in frontend/ (looked in {static_dir})",
                },
            )

    return app
