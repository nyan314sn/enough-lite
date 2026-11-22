"""Enough Lite API (FastAPI). The React build in web/dist is served at /.

Endpoints: /api/health, /api/intake, /api/plan (Server-Sent Events), /api/ask, /api/costs.
Deploy-ready: one start command (run.py reads PORT), hard dollar caps (llm.py), a per-IP rate limit on /api/plan and
/api/ask, and no secrets or prompts in logs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config, llm, pipeline, safety, samples
from .agents import intake, parser as _parser
from .agents.base import RunCtx
from .schemas import AskRequest, IntakeRequest, IntakeResponse, PlanRequest, Profile

log = logging.getLogger("enough_lite")
app = FastAPI(title="Enough Lite", docs_url="/api/docs", openapi_url="/api/openapi.json")

# ------------------------------------------------------------------ security headers and a request size cap
# The built app loads only its own script and stylesheet, uses system fonts, a data: favicon and fetch() to /api.
# React sets inline styles through the DOM (element.style), which a strict style-src allows.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self' data:; "
       "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
SECURITY_HEADERS = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"), (b"cross-origin-opener-policy", b"same-origin")]
TOO_LARGE = b'{"detail":"That request is too large. Please send less text."}'


def max_body_bytes() -> int:
    try:
        return int(os.getenv("ENOUGH_MAX_BODY_BYTES", "1000000"))
    except ValueError:
        return 1_000_000


class SecurityMiddleware:
    """Pure ASGI (safe with the plan's event stream): adds the security headers to every response and refuses
    request bodies over ENOUGH_MAX_BODY_BYTES (default 1 MB) with 413, whether or not Content-Length is sent."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit_ = max_body_bytes()
        started = False
        over = False            # the body ran past the cap: whatever the app answers becomes a 413
        docs = scope.get("path", "").startswith(("/api/docs", "/api/redoc"))   # Swagger UI loads from a CDN

        async def send_(message):
            nonlocal started
            if over and not started and message["type"] == "http.response.start":
                started = True
                await too_large()
                return
            if over and message["type"] == "http.response.body":
                return
            if message["type"] == "http.response.start":
                started = True
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in {h for h, _ in SECURITY_HEADERS}]
                headers += SECURITY_HEADERS
                if not docs:
                    headers.append((b"content-security-policy", CSP.encode()))
                message = {**message, "headers": headers}
            await send(message)

        async def too_large():
            await send({"type": "http.response.start", "status": 413,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(TOO_LARGE)).encode()),
                                    *SECURITY_HEADERS, (b"content-security-policy", CSP.encode())]})
            await send({"type": "http.response.body", "body": TOO_LARGE})

        for k, v in scope.get("headers", []):
            if k == b"content-length":
                try:
                    if int(v) > limit_:
                        return await too_large()
                except ValueError:
                    return await too_large()
        seen = 0

        async def receive_():
            nonlocal seen, over
            if over:
                return {"type": "http.request", "body": b"", "more_body": False}
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit_:
                    over = True        # stop reading; the app sees a cut body and its answer is replaced by a 413
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        await self.app(scope, receive_, send_)


app.add_middleware(SecurityMiddleware)


def _log_safe(text: str) -> str:
    """No CR, LF or other control characters in a log line (a path or value cannot forge a second line)."""
    return "".join(c if c.isprintable() else "?" for c in (text or ""))[:200]


# ------------------------------------------------------------------ errors: always {"detail": "<plain message>"}
@app.exception_handler(RequestValidationError)
async def _bad_request(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Some of what was sent could not be read. Please check it and try again."})


@app.exception_handler(Exception)
async def _server_error(request: Request, exc: Exception):
    log.error("unhandled error on %s: %s", _log_safe(request.url.path), type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


TOO_BIG = pipeline.BAD_PROFILE      # same plain message as other bad profiles


def check_shape(value, **limits) -> None:
    """The profile and plan travel with every request: refuse oversized ones before any work (400)."""
    if not safety.shape_ok(value, **limits):
        raise HTTPException(status_code=400, detail=TOO_BIG)


# ------------------------------------------------------------------ sessions and rate limit
def client_ip(request: Request) -> str:
    if config.get_settings().trust_proxy:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def session_id(request: Request) -> str:
    sid = (request.headers.get("x-session-id") or "").strip()
    if sid and len(sid) <= 64 and sid.replace("-", "").replace("_", "").isalnum():
        return sid
    return "ip:" + client_ip(request)


def test_mode(request: Request) -> bool:
    """X-Enough-Test: 1 lifts the rate limit, only when the server sets ENOUGH_TEST_MODE=1. Dollar caps still apply."""
    return os.getenv("ENOUGH_TEST_MODE", "0") == "1" and request.headers.get("x-enough-test") == "1"


class RateLimiter:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, per_minute: int | None = None, per_day: int | None = None) -> str | None:
        s = config.get_settings()
        per_minute = s.rate_per_minute if per_minute is None else per_minute
        per_day = s.rate_per_day if per_day is None else per_day
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > 86400:
            q.popleft()
        last_min = sum(1 for t in q if now - t < 60)
        if last_min >= per_minute:
            return "Too many requests in the last minute. Please wait a minute and try again."
        if len(q) >= per_day:
            return "You have reached today's limit for this app. Please come back tomorrow."
        q.append(now)
        return None


LIMITER = RateLimiter()


def limit(request: Request) -> None:
    if test_mode(request):
        return
    msg = LIMITER.check(client_ip(request))
    if msg:
        raise HTTPException(status_code=429, detail=msg)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def limit_intake(request: Request) -> None:
    """Intake is a chat (one request per answer), so it has its own, looser per-IP limit. It can call the model, so
    without a limit one client could spend the shared total cap by changing its session id."""
    if test_mode(request):
        return
    msg = LIMITER.check("intake:" + client_ip(request), _env_int("ENOUGH_INTAKE_RATE_PER_MINUTE", 40),
                        _env_int("ENOUGH_INTAKE_RATE_PER_DAY", 600))
    if msg:
        raise HTTPException(status_code=429, detail=msg)


def emergency_intake(profile_so_far: dict | None) -> IntakeResponse:
    """The fixed emergency message. The profile comes back unchanged; no question is asked."""
    try:
        p = Profile.model_validate(profile_so_far or {})
    except Exception:
        p = Profile()
    try:
        flds, miss = intake.fields(p), intake.missing(p)
    except Exception:
        flds, miss = [], []
    return IntakeResponse(profile=p.model_dump(), fields=flds, missing=miss, question=None, reply=safety.EMERGENCY_REPLY)


# ------------------------------------------------------------------ API
@app.get("/api/health")
async def health():
    s = config.get_settings()
    return {"status": "ok", "provider": s.provider, "model": s.model, "ai_available": s.has_key,
            "budget": {"run_usd": s.run_budget_usd, "session_usd": s.session_budget_usd}}


@app.get("/api/samples")
async def api_samples():
    """Sample households for the admin screen (?admin). Fixed data from a file, each with the page-1 state ("intake"): no model call, no secrets, no limit."""
    return samples.load()


MODEL_COMPARE_PATH = Path(__file__).resolve().parent.parent / "eval" / "model_compare" / "summary.json"


@app.get("/api/admin/model-compare")
async def api_model_compare():
    """The saved model comparison (eval/model_compare/summary.json) for the admin page. Read-only; no secrets and no per-user data."""
    try:
        return json.loads(MODEL_COMPARE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="No model comparison has been saved yet.")


@app.post("/api/intake")
async def api_intake(req: IntakeRequest, request: Request):
    check_shape(req.profile_so_far)
    if safety.is_emergency(req.text):   # before any model call; the plan is left as it was
        return emergency_intake(req.profile_so_far)
    limit_intake(request)
    return await intake.run(req.text, req.profile_so_far, session=session_id(request), reset=req.reset or None)


@app.post("/api/plan")
async def api_plan(req: PlanRequest, request: Request):
    check_shape(req.profile)
    limit(request)
    try:
        profile = pipeline.prepare(req.profile)
    except pipeline.PlanError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail=pipeline.BAD_PROFILE)
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    ctx = RunCtx(profile=profile, session=session_id(request), emit=emit)

    async def worker():
        try:
            await pipeline.run_plan(ctx)
        except Exception as exc:
            log.error("plan failed: %s", type(exc).__name__)
            await queue.put({"type": "error", "message": "The plan could not be finished. Please try again."})
        finally:
            await queue.put({"type": "done"})

    async def stream():
        task = asyncio.create_task(worker())
        try:
            while True:
                ev = await queue.get()
                yield f"data: {json.dumps(ev)}\n\n"
                if ev["type"] == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/ask")
async def api_ask(req: AskRequest, request: Request):
    check_shape(req.profile)
    check_shape(req.pending_change)
    check_shape(req.plan, max_list=400, max_str=4000, max_nodes=40000)
    if safety.is_emergency(req.question):   # before any model call; no plan changes
        return {"kind": "refused", "emergency": True, "text": safety.EMERGENCY_REPLY, "citations": [],
                "tokens": {"input": 0, "cached": 0, "output": 0}, "cost_usd": 0.0}
    limit(request)
    if not safety.is_refusable(req.question) and not safety.is_medicaid_hiding(req.question):
        try:
            pipeline.prepare(req.profile)    # a bad profile is a 400, never a 500
        except pipeline.PlanError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            raise HTTPException(status_code=400, detail=pipeline.BAD_PROFILE)
    try:
        return await pipeline.ask(_parser.fix_words(req.question), req.profile, session=session_id(request), pending=req.pending_change, plan_so_far=req.plan)
    except pipeline.PlanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/reset")
async def api_reset(request: Request):
    """Start over. The server keeps no draft (the profile travels with each request), so this clears the session's
    cost log and plan history. It does NOT clear the spend counter: the session and total dollar caps still hold."""
    sid = session_id(request)
    hidden = llm.METER.clear_history(sid)
    return {"ok": True, "session": sid, "cleared_entries": hidden, "profile": {},
            "spent_usd": round(llm.METER.spent(session=sid), 6), "session_cap_usd": config.get_settings().session_budget_usd}


@app.get("/api/costs")
async def api_costs(request: Request, scope: str = "session"):
    # every session's log (with session ids and client IPs) is for the test kit only, not for any visitor
    if scope == "all" and not test_mode(request):
        raise HTTPException(status_code=403, detail="Only this session's costs are shown.")
    sid = None if scope == "all" else session_id(request)
    out = llm.METER.summary(sid)
    out["session"] = sid or "all"
    return out


# ------------------------------------------------------------------ the web app
if config.WEB_DIST.is_dir():
    assets = config.WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        f = (config.WEB_DIST / path).resolve()
        if path and f.is_file() and config.WEB_DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(config.WEB_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"detail": "The web app is not built. The API is at /api/health."}
