"""
Moorchid FastAPI backend — exposes the journal, chat, and poetry agents as REST APIs.
All endpoints (except health and auth) require a valid JWT token.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, Sequence

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ── ensure project root is on sys.path ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── business logic ─────────────────────────────────────────────────────────────
from models import (
    JournalEntry,
    PoetryReport,
    User,
    add_chat_message,
    add_conversation_message,
    add_entry,
    clear_user_chat_history,
    count_user_conversations,
    create_conversation,
    create_user,
    delete_conversation,
    delete_entry,
    ensure_default_conversation,
    get_conversation,
    get_conversation_messages,
    get_entry_by_id,
    get_latest_poetry_report,
    get_long_term_themes,
    get_poetry_reports,
    get_user_by_username,
    get_user_chat_history,
    get_user_conversations,
    get_user_entries,
    get_user_memories,
    init_db,
    journal_window,
    save_memories,
    save_memory,
    save_poetry_report,
    touch_conversation,
    update_conversation_title,
    update_entry,
    verify_user,
)
from agents import index_memory, run_poet_agent, run_soul_chat, run_soul_chat_stream, serialize_analysis
from vector_store import get_vector_store
from config import get_config
from memory_schema import (
    assemble_prompt_memory,
    canonicalize_emotion,
    valence_for_emotion,
    memories_from_pattern,
    stage_memory_from_poet,
    suggest_long_term,
)

LOGGER = logging.getLogger(__name__)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── SSE ───────────────────────────────────────────────────────────────────────
from sse_starlette.sse import EventSourceResponse

# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Moorchid API",
    version="2.0.0",
    description="Personal journal, memory-grounded companion chat, and poetic weekly summary.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
#
# We want the best of both worlds:
#   • Credentialed requests (cookies / Authorization headers) must be
#     allowed for explicit origins like http://localhost:3000 and
#     http://42.194.168.71:3000.
#   • Cross-origin requests from any other origin (e.g. a phone on
#     192.168.x.x hitting its own IP:3000) should also work for the
#     non-credentialed case.
#
# Starlette forbids `allow_origins=["*"]` together with
# `allow_credentials=True` — it raises at startup. So we split: the
# explicit list is fed into CORSMiddleware with credentials, and we add
# a *separate* tiny middleware that echoes whatever origin came in for
# non-credentialed requests. That way the browser is never told
# "Disallowed CORS origin" again in dev.
cfg = get_config()

EXPLICIT_ORIGINS = [o for o in cfg.cors_allowed_origins if o != "*"]
WILDCARD = "*" in cfg.cors_allowed_origins

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from starlette.requests import Request as StarletteRequest


class MoorchidCORSMiddleware(BaseHTTPMiddleware):
    """Hand-rolled CORS middleware.

    Replaces Starlette's `CORSMiddleware` because that one refuses any
    unknown origin (400) and doesn't play nicely with `*` + credentials.

    Behaviour:
      • If the request's Origin is in `EXPLICIT_ORIGINS`, the response
        echoes that Origin and sets Allow-Credentials.
      • Else if `WILDCARD` is enabled (dev only), the response echoes the
        Origin without Allow-Credentials.
      • Else the request is passed through untouched (server-to-server
        or same-origin — no CORS response needed).

    Preflight (OPTIONS) is answered directly with 204 so the browser
    never has to wait for the route to run.
    """

    async def dispatch(
        self, request: StarletteRequest, call_next
    ) -> StarletteResponse:
        origin = request.headers.get("origin")
        is_preflight = (
            request.method == "OPTIONS"
            and "access-control-request-method" in request.headers
        )

        # Handle preflight inline — no need to forward to the app.
        if is_preflight:
            resp = StarletteResponse(status_code=204)
        else:
            resp = await call_next(request)

        if origin:
            allowed = origin in EXPLICIT_ORIGINS
            if allowed:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Vary"] = "Origin"
            elif WILDCARD:
                # Echo origin but without credentials — browser will
                # refuse to send Authorization on its own, so this is
                # safe for unauthenticated endpoints.
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Vary"] = "Origin"
            else:
                # Last-resort allow: same scheme + hostname without
                # explicit port match. When the SPA is served from the
                # same origin that nginx uses to reverse-proxy the API
                # (e.g. http://cloverspace.cn → /api/...), every
                # request is technically same-origin and never needs
                # CORS. Mobile browsers can however upgrade the
                # request to a cross-origin one when the dev bundle
                # was loaded from a different IP during testing, in
                # which case echoing the origin keeps things working
                # without weakening security: only origins that
                # already reached us over HTTP get a response, and
                # there is no Allow-Credentials so the JWT header is
                # the only thing protecting the API.
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Vary"] = "Origin"

            if is_preflight:
                resp.headers.setdefault(
                    "Access-Control-Allow-Methods",
                    "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
                )
                resp.headers.setdefault(
                    "Access-Control-Allow-Headers",
                    request.headers.get(
                        "access-control-request-headers", "*"
                    ),
                )
                resp.headers.setdefault("Access-Control-Max-Age", "600")

        return resp


if cfg.environment == "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=EXPLICIT_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(MoorchidCORSMiddleware)


# ── OPTIONS preflight fast-path ───────────────────────────────────────────────
#
# FastAPI only matches routes against the methods they declare, so an
# `OPTIONS /api/...` preflight normally never enters a route handler. However
# some proxies (and some custom middleware) can intercept or block OPTIONS
# before CORS runs. As a defensive measure we install an explicit
# catch-all OPTIONS handler that returns 204 immediately. Because it's
# registered AFTER CORSMiddleware below, it also benefits from the proper
# `Access-Control-Allow-*` response headers that the middleware injects.

from fastapi.responses import Response


@app.options("/{full_path:path}", include_in_schema=False)
async def preflight(full_path: str) -> Response:
    """Handle every preflight (OPTIONS) request with 204 No Content.

    CORSMiddleware (registered above) will add the appropriate
    `Access-Control-Allow-*` headers before this handler returns,
    so the browser sees a valid preflight response.
    """
    return Response(status_code=204)


# ── startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup() -> None:
    init_db()
    cfg = get_config()
    LOGGER.info(
        "DeepSeek %s (key %s) · env file %s",
        "ON" if cfg.deepseek_enabled else "OFF",
        "present" if cfg.deepseek_api_key else "missing",
        "found" if (PROJECT_ROOT / ".env").exists() else "missing",
    )


# ── diagnostics: friendly 404 / 405 with the actual path ──────────────────────
#
# The SPA bundles SPA-style 404s by default ("Not Found" + no body), which is
# useless for debugging reverse-proxy routing mismatches. Replace them with a
# JSON payload that echoes the path the server actually saw so the frontend
# (and nginx access logs) make it obvious whether `/api` was stripped,
# duplicated, or otherwise mangled upstream.
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException) -> JSONResponse:
    LOGGER.info(
        "404 on %s %s (origin=%s, referer=%s)",
        request.method, request.url.path,
        request.headers.get("origin"), request.headers.get("referer"),
    )
    return JSONResponse(
        status_code=404,
        content={
            "detail": (
                f"No route matches {request.method} {request.url.path}. "
                "If you reached the API via a reverse proxy, double-check "
                "that `/api` is forwarded as-is and not stripped/duplicated."
            )
        },
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: HTTPException) -> JSONResponse:
    LOGGER.info(
        "405 on %s %s (origin=%s, referer=%s)",
        request.method, request.url.path,
        request.headers.get("origin"), request.headers.get("referer"),
    )
    return JSONResponse(
        status_code=405,
        content={
            "detail": (
                f"Method {request.method} not allowed on {request.url.path}."
            )
        },
    )


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _cfg():
    return get_config()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = dict(data)
    cfg = _cfg()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=cfg.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def decode_token(token: str) -> str:
    """Decode a JWT and return the username (subject). Raises HTTPException on failure."""
    cfg = _cfg()
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
        username: str | None = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    """
    FastAPI dependency — extracts and validates the JWT from the
    Authorization: Bearer <token> header and returns the corresponding User.

    Usage in route handlers::

        @app.get("/api/entries")
        def list_entries(user: User = Depends(get_current_user)):
            ...
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = decode_token(token)
    user = get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: str


class EntryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    mood: Optional[str] = Field(default=None, description="User-selected mood. If absent, Pattern Agent infers it.")


class EntryUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    emotion: str = Field(..., min_length=1, max_length=16)
    tags: list[str] = Field(..., min_length=1, max_length=3)


class EntryResponse(BaseModel):
    id: int
    user_id: str
    content: str
    emotion: str
    tags: list[str]
    created_at: str
    created_at_epoch: float
    valence: float = 0.0
    intensity: float = 0.55
    analysis: Optional[dict[str, Any]] = None


class JournalWindow(BaseModel):
    entries: list[EntryResponse]
    has_earlier: bool


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation thread id. Created on first send if missing.",
    )
    anchor_entry_id: Optional[int] = Field(
        default=None,
        description="Optional journal entry to ground this turn.",
    )


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        description="Optional initial title; auto-generated from the first message otherwise.",
    )
    anchor_entry_id: Optional[int] = Field(
        default=None,
        description="Journal entry this conversation continues from.",
    )


class ConversationRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=64)


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    anchor_entry_id: Optional[int] = None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    page: int
    page_size: int
    total: int


class PoetryResponse(BaseModel):
    id: int
    user_id: str
    title: str
    poetry_content: str
    quote: str
    quote_author: str
    activity: str | None = None
    emotion_distribution: str
    created_at: str


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]


class HealthResponse(BaseModel):
    status: str
    deepseek_enabled: bool
    zhipuai_enabled: bool


# ── helpers ────────────────────────────────────────────────────────────────────

def _entry_to_resp(entry: JournalEntry) -> EntryResponse:
    analysis = None
    raw = entry.get("analysis_json")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                analysis = parsed
        except (json.JSONDecodeError, TypeError):
            analysis = None
    return EntryResponse(
        id=entry["id"],
        user_id=entry["user_id"],
        content=entry["content"],
        emotion=entry["emotion"],
        tags=entry["tags"],
        created_at=entry["created_at"],
        created_at_epoch=datetime.fromisoformat(entry["created_at"]).timestamp(),
        valence=float(entry.get("valence") or 0.0),
        intensity=float(entry.get("intensity") or 0.55),
        analysis=analysis,
    )


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    cfg = get_config()
    return HealthResponse(
        status="ok",
        deepseek_enabled=cfg.deepseek_enabled,
        zhipuai_enabled=cfg.zhipuai_enabled,
    )


# ── /api/auth ─────────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=UserResponse, status_code=201)
def register(body: UserRegister) -> UserResponse:
    """Register a new user account. Username must be unique."""
    try:
        user = create_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return UserResponse(
        id=user["id"],
        username=user["username"],
        created_at=user["created_at"],
    )


# Bare-prefix alias — covers the common nginx misconfiguration where
# `location /api/ { proxy_pass http://127.0.0.1:8000; }` (no trailing
# slash on the upstream) rewrites `/api/auth/login` to `/auth/login`.
# Keeping both variants mounted means the API stays reachable regardless
# of whether the reverse proxy preserves or strips the `/api` prefix.
@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register_alias(body: UserRegister) -> UserResponse:
    return register(body)


@app.post("/api/auth/login", response_model=Token)
def login(body: UserLogin) -> Token:
    """Authenticate with username + password and return a JWT."""
    user = verify_user(body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user["username"]})
    return Token(access_token=access_token)


@app.post("/auth/login", response_model=Token)
def login_alias(body: UserLogin) -> Token:
    return login(body)


# ── /api/entries ──────────────────────────────────────────────────────────────

@app.get("/api/entries", response_model=list[EntryResponse])
def list_entries(
    user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
) -> list[EntryResponse]:
    entries = get_user_entries(user["username"], limit=limit, offset=max(0, offset))
    return [_entry_to_resp(e) for e in entries]


@app.get("/api/journal/window", response_model=JournalWindow)
def read_journal_window(start: datetime, end: datetime, user: User = Depends(get_current_user)):
    if start.tzinfo is None or end.tzinfo is None or not timedelta(0) < end - start <= timedelta(days=32):
        raise HTTPException(status_code=422, detail="Expected a dated window of up to 32 days")
    rows, earlier = journal_window(
        user["username"],
        start.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        end.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    )
    return JournalWindow(entries=[_entry_to_resp(row) for row in rows], has_earlier=earlier)


@app.post("/api/entries", response_model=EntryResponse, status_code=201)
def create_entry(
    body: EntryCreate,
    user: User = Depends(get_current_user),
) -> EntryResponse:
    from agents import run_pattern_agent

    if body.mood and body.mood.strip():
        emotion = canonicalize_emotion(body.mood)
        pattern = run_pattern_agent(body.content)
        pattern["emotion"] = emotion
        pattern["valence"] = valence_for_emotion(emotion)
        tags = pattern["tags"]
    else:
        pattern = run_pattern_agent(body.content)
        emotion = pattern["emotion"]
        tags = pattern["tags"]

    analysis_json = serialize_analysis(pattern)
    entry_id = add_entry(
        user_id=user["username"],
        content=body.content,
        emotion=emotion,
        tags=tags,
        valence=pattern["valence"],
        intensity=pattern["intensity"],
        analysis_json=analysis_json,
    )

    try:
        event_memories = memories_from_pattern(
            user_id=user["username"],
            entry_id=entry_id,
            content=body.content,
            extraction=pattern,
        )
        save_memories(event_memories)
        existing_themes = get_long_term_themes(user["username"])
        recent_events = get_user_memories(user["username"], layer="event", limit=80)
        promoted = suggest_long_term(recent_events, existing_themes)
        if promoted:
            save_memories(promoted)
    except Exception as exc:
        LOGGER.warning("Failed to persist layered memories for entry %s: %s", entry_id, exc)

    try:
        index_memory(
            user_id=user["username"],
            entry_id=entry_id,
            content=body.content,
            metadata={
                "emotion": pattern["emotion"],
                "tags": pattern["tags"],
                "valence": pattern["valence"],
                "themes": pattern["themes"],
            },
        )
    except Exception as exc:
        LOGGER.warning("Failed to index journal entry %s in vector store: %s", entry_id, exc)

    entry = get_entry_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created entry")
    return _entry_to_resp(entry)


@app.delete("/api/entries/{entry_id}", status_code=204)
def remove_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
) -> None:
    entry = get_entry_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry["user_id"] != user["username"]:
        raise HTTPException(status_code=403, detail="Not your entry")

    deleted = delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")

    try:
        get_vector_store().delete([entry_id])
    except Exception as exc:
        LOGGER.warning("Failed to delete entry %s from vector store: %s", entry_id, exc)


@app.patch("/api/entries/{entry_id}", response_model=EntryResponse)
def modify_entry(
    entry_id: int,
    body: EntryUpdate,
    user: User = Depends(get_current_user),
) -> EntryResponse:
    entry = get_entry_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry["user_id"] != user["username"]:
        raise HTTPException(status_code=403, detail="Not your entry")

    updated = update_entry(
        entry_id=entry_id,
        content=body.content,
        emotion=body.emotion,
        tags=body.tags,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")

    entry = get_entry_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated entry")
    return _entry_to_resp(entry)


# ── /api/chat/stream (SSE) ────────────────────────────────────────────────────

# How many most-recent chat messages to inject into the LLM prompt.
# All messages are stored in the DB; only this slice counts against the
# model's context window.  15 messages ≈ 7–8 conversation turns.
MAX_CHAT_CONTEXT_MESSAGES = 15


@app.get("/api/chat/stream")
def chat_stream_get():
    async def event_generator():
        yield {"event": "connected", "data": json.dumps({"status": "ok"})}
        while True:
            await asyncio.sleep(25)
            yield {"event": "ping", "data": ""}

    return EventSourceResponse(event_generator())


def _layered_memory_prompt(username: str) -> str:
    events = get_user_memories(username, layer="event", limit=12)
    stage = get_user_memories(username, layer="stage", limit=3)
    long_term = get_user_memories(username, layer="long_term", limit=8)
    return assemble_prompt_memory(events=events, stage=stage, long_term=long_term)


def _build_chat_context(
    username: str, conversation_id: str
) -> tuple[list[JournalEntry], list[dict[str, str]], str, Optional[JournalEntry]]:
    """Return journal entries + trimmed chat history + layered memory + optional anchor."""
    history_entries = get_user_entries(username, limit=12)
    db_history = get_conversation_messages(conversation_id, limit=200)
    trimmed = db_history[-MAX_CHAT_CONTEXT_MESSAGES:]
    chat_history_dicts: list[dict[str, str]] = [
        {"role": m["role"], "content": m["content"]}
        for m in trimmed
    ]
    conv = get_conversation(conversation_id)
    anchor = None
    if conv and conv.get("anchor_entry_id"):
        candidate = get_entry_by_id(int(conv["anchor_entry_id"]))
        if candidate and candidate["user_id"] == username:
            anchor = candidate
    try:
        layered = _layered_memory_prompt(username)
    except Exception as exc:
        LOGGER.warning("Failed to assemble layered memory for %s: %s", username, exc)
        layered = ""
    return history_entries, chat_history_dicts, layered, anchor


def _resolve_conversation_for_send(
    username: str, requested_id: Optional[str]
) -> ConversationResponse:
    """Return the conversation row for an incoming chat request.

    If the client did not pass an id, or passed ``'default'`` (legacy
    callers), ensure the user's "default" conversation exists and use
    it. Any other id is validated strictly against ownership.
    """
    if requested_id:
        conv = get_conversation(requested_id)
        if conv is None or conv["user_id"] != username:
            raise HTTPException(
                status_code=404, detail="Conversation not found"
            )
        return ConversationResponse(
            id=conv["id"],
            user_id=conv["user_id"],
            title=conv["title"],
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            anchor_entry_id=conv.get("anchor_entry_id"),
        )

    conv = ensure_default_conversation(username)
    return ConversationResponse(
        id=conv["id"],
        user_id=conv["user_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        anchor_entry_id=conv.get("anchor_entry_id"),
    )


def _derive_title_from_message(text: str, max_chars: int = 20) -> str:
    """Slice the leading message into a short, human-friendly title."""
    stripped = text.strip().replace("\n", " ")
    if len(stripped) <= max_chars:
        return stripped
    head = stripped[:max_chars]
    # Avoid ending on a half-cut sentence — step back to the last whitespace
    # so the rendered title doesn't look broken.
    if " " in head and max_chars < len(stripped):
        head = head.rsplit(" ", 1)[0]
    return head + "…"


@app.post("/api/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
):
    username = user["username"]
    conv = _resolve_conversation_for_send(username, body.conversation_id)
    conversation_id = conv.id

    # Persist user message before streaming. If the conversation is still
    # at its default title, upgrade it to a slice of the first user message.
    try:
        add_conversation_message(username, conversation_id, "user", body.message)
    except Exception as exc:
        LOGGER.warning("Failed to persist user message for %s: %s", username, exc)

    current = get_conversation(conversation_id)
    if current and current["title"] in ("新对话", "历史对话"):
        new_title = _derive_title_from_message(body.message)
        try:
            update_conversation_title(conversation_id, new_title)
        except Exception as exc:
            LOGGER.warning("Failed to auto-title conversation %s: %s", conversation_id, exc)

    async def event_generator():
        history_entries, chat_history_dicts, layered, anchor = _build_chat_context(
            username, conversation_id
        )
        if body.anchor_entry_id and anchor is None:
            candidate = get_entry_by_id(body.anchor_entry_id)
            if candidate and candidate["user_id"] == username:
                anchor = candidate

        full_reply = ""
        try:
            async for token in run_soul_chat_stream(
                user_input=body.message,
                history_entries=history_entries,
                chat_history=chat_history_dicts,
                layered_memory=layered or None,
                anchor_entry=anchor,
            ):
                full_reply += token
                yield {
                    "event": "message",
                    "data": json.dumps({"content": token}),
                }
        except asyncio.CancelledError:
            # Client disconnected mid-stream — not a real error.
            LOGGER.info("SSE stream cancelled for user %s", username)
        except Exception as exc:
            LOGGER.warning("SSE stream exception for %s: %s", username, exc)

        # Always try to persist whatever reply we collected, even on
        # partial stream or clean disconnect.  This handles three cases:
        #   1. Normal completion  → full reply is saved.
        #   2. Client disconnect  → partial reply is saved.
        #   3. Model exception    → non-empty partial is saved.
        if full_reply:
            try:
                add_conversation_message(username, conversation_id, "assistant", full_reply)
            except Exception as exc:
                LOGGER.warning("Failed to persist assistant reply for %s: %s", username, exc)

        # Always emit finished so the frontend never hangs waiting for it.
        yield {"event": "message", "data": json.dumps({"finished": True})}

    return EventSourceResponse(event_generator())


@app.post("/api/chat")
@limiter.limit("20/minute")
def chat_nonstream(
    request: Request,
    body: ChatRequest,
    user: User = Depends(get_current_user),
):
    """Non-streaming chat — falls back when SSE is unavailable."""
    username = user["username"]
    conv = _resolve_conversation_for_send(username, body.conversation_id)
    conversation_id = conv.id

    # Persist user message
    try:
        add_conversation_message(username, conversation_id, "user", body.message)
    except Exception as exc:
        LOGGER.warning("Failed to persist user message for %s: %s", username, exc)

    current = get_conversation(conversation_id)
    if current and current["title"] in ("新对话", "历史对话"):
        new_title = _derive_title_from_message(body.message)
        try:
            update_conversation_title(conversation_id, new_title)
        except Exception as exc:
            LOGGER.warning("Failed to auto-title conversation %s: %s", conversation_id, exc)

    history_entries, chat_history_dicts, layered, anchor = _build_chat_context(
        username, conversation_id
    )
    if body.anchor_entry_id and anchor is None:
        candidate = get_entry_by_id(body.anchor_entry_id)
        if candidate and candidate["user_id"] == username:
            anchor = candidate
    try:
        reply = run_soul_chat(
            user_input=body.message,
            history_entries=history_entries,
            chat_history=chat_history_dicts,
            layered_memory=layered or None,
            anchor_entry=anchor,
        )
    except Exception as exc:
        LOGGER.warning("Chat non-stream failed for user %s: %s", username, exc)
        reply = (
            "抱歉，我现在有点走神了 🌿。"
            "也许可以换个话题，或者先去【✍️ 随手记】记录一下此刻的心情？"
        )

    # Persist assistant reply
    try:
        add_conversation_message(username, conversation_id, "assistant", reply)
    except Exception as exc:
        LOGGER.warning("Failed to persist assistant reply for %s: %s", username, exc)

    return {
        "reply": reply,
        "conversation_id": conversation_id,
    }


# ── /api/chat/history ─────────────────────────────────────────────────────────

@app.get("/api/chat/history", response_model=ChatHistoryResponse)
def get_chat_history(
    user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
) -> ChatHistoryResponse:
    """Return the authenticated user's chat history, oldest first."""
    records = get_user_chat_history(user["username"], limit=limit, offset=offset)
    return ChatHistoryResponse(
        messages=[
            ChatHistoryMessage(role=m["role"], content=m["content"])
            for m in records
        ]
    )


@app.delete("/api/chat/history", status_code=204)
def clear_chat_history(user: User = Depends(get_current_user)) -> None:
    """Delete all chat history for the authenticated user."""
    clear_user_chat_history(user["username"])


# ── /api/conversations ────────────────────────────────────────────────────────


def _conversation_to_resp(conv) -> ConversationResponse:
    return ConversationResponse(
        id=conv["id"],
        user_id=conv["user_id"],
        title=conv["title"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        anchor_entry_id=conv.get("anchor_entry_id"),
    )


@app.post("/api/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation_route(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
) -> ConversationResponse:
    """Create a new (empty) conversation owned by the current user."""
    conv = create_conversation(
        user["username"],
        title=(body.title or "新对话").strip() or "新对话",
        anchor_entry_id=body.anchor_entry_id,
    )
    return _conversation_to_resp(conv)


@app.get("/api/conversations", response_model=ConversationListResponse)
def list_conversations(
    user: User = Depends(get_current_user),
    page: int = 1,
    page_size: int = 30,
) -> ConversationListResponse:
    """Return conversations ordered by most-recent-activity first."""
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 100))
    items = get_user_conversations(user["username"], safe_page, safe_page_size)
    total = count_user_conversations(user["username"])
    return ConversationListResponse(
        conversations=[_conversation_to_resp(c) for c in items],
        page=safe_page,
        page_size=safe_page_size,
        total=total,
    )


@app.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=ChatHistoryResponse,
)
def get_conversation_messages_route(
    conversation_id: str,
    user: User = Depends(get_current_user),
    limit: int = 200,
    offset: int = 0,
) -> ChatHistoryResponse:
    """Return the messages of one conversation the user owns."""
    conv = get_conversation(conversation_id)
    if conv is None or conv["user_id"] != user["username"]:
        # Hide existence: a foreign id is indistinguishable from "missing".
        raise HTTPException(status_code=404, detail="Conversation not found")
    records = get_conversation_messages(
        conversation_id, limit=max(1, min(limit, 500)), offset=max(0, offset)
    )
    return ChatHistoryResponse(
        messages=[
            ChatHistoryMessage(role=m["role"], content=m["content"])
            for m in records
        ]
    )


@app.patch(
    "/api/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def rename_conversation_route(
    conversation_id: str,
    body: ConversationRename,
    user: User = Depends(get_current_user),
) -> ConversationResponse:
    conv = get_conversation(conversation_id)
    if conv is None or conv["user_id"] != user["username"]:
        raise HTTPException(status_code=404, detail="Conversation not found")
    ok = update_conversation_title(conversation_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    refreshed = get_conversation(conversation_id)
    assert refreshed is not None  # we just updated it
    return _conversation_to_resp(refreshed)


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def delete_conversation_route(
    conversation_id: str,
    user: User = Depends(get_current_user),
) -> None:
    conv = get_conversation(conversation_id)
    if conv is None or conv["user_id"] != user["username"]:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")


# ── /api/poetry ───────────────────────────────────────────────────────────────

@app.get("/api/poetry", response_model=list[PoetryResponse])
def list_poetry(
    user: User = Depends(get_current_user),
    limit: int = 10,
) -> list[PoetryResponse]:
    reports = get_poetry_reports(user["username"], limit=limit)
    responses = []
    for r in reports:
        try:
            blessing_data = json.loads(r["blessing"])
            activity = blessing_data.get("activity")
            quote = blessing_data.get("quote", "")
            quote_author = blessing_data.get("quote_author", "")
        except Exception as exc:
            LOGGER.warning("Failed to parse blessing JSON for poetry report %s: %s", r["id"], exc)
            activity = None
            quote = ""
            quote_author = ""
        responses.append(PoetryResponse(
            id=r["id"],
            user_id=r["user_id"],
            title=r["title"],
            poetry_content=r["poetry_content"],
            quote=quote,
            quote_author=quote_author,
            activity=activity,
            emotion_distribution=r["emotion_distribution"],
            created_at=r["created_at"],
        ))
    return responses


@app.post("/api/poetry/generate", response_model=PoetryResponse, status_code=201)
@limiter.limit("5/hour")
def generate_poetry(request: Request, user: User = Depends(get_current_user)) -> PoetryResponse:
    """Generate a weekly poetry report for the authenticated user. Rate-limited to 1/hour."""
    existing = get_latest_poetry_report(user["username"])
    if existing:
        try:
            last_time = datetime.strptime(existing["created_at"], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last_time).total_seconds() < 3600:
                raise HTTPException(
                    status_code=429,
                    detail="A poetry report was already generated within the last hour. Please try again later.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            LOGGER.warning("Failed to parse poetry report timestamp for rate-check: %s", exc)

    entries = get_user_entries(user["username"], limit=50)
    if len(entries) < 3:
        raise HTTPException(
            status_code=422,
            detail="At least 3 journal entries are required to generate a poetry report.",
        )

    poet = run_poet_agent(user_name="朋友", entries=entries)
    report_id = save_poetry_report(
        user_id=user["username"],
        title=poet["title"],
        poetry_content=poet["poetry_content"],
        emotion_distribution=poet["emotion_dist"],
        blessing=json.dumps({"quote": poet["quote"], "quote_author": poet["quote_author"], "activity": poet.get("activity")}, ensure_ascii=False),
    )
    try:
        save_memory(
            stage_memory_from_poet(
                user_id=user["username"],
                title=poet["title"],
                poetry_content=poet["poetry_content"],
                emotion_dist=poet["emotion_dist"],
                entry_ids=[e["id"] for e in entries],
            )
        )
    except Exception as exc:
        LOGGER.warning("Failed to persist stage memory for poetry %s: %s", report_id, exc)

    all_reports = get_poetry_reports(user["username"], limit=1)
    report = next((r for r in all_reports if r["id"] == report_id), None)
    if report is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve generated poetry report")

    blessing_data = json.loads(report["blessing"])
    return PoetryResponse(
        id=report["id"],
        user_id=report["user_id"],
        title=report["title"],
        poetry_content=report["poetry_content"],
        quote=blessing_data.get("quote", ""),
        quote_author=blessing_data.get("quote_author", ""),
        activity=blessing_data.get("activity"),
        emotion_distribution=report["emotion_distribution"],
        created_at=report["created_at"],
    )


class MemoryResponse(BaseModel):
    id: str
    layer: str
    content: str
    summary: Optional[str] = None
    emotion: Optional[str] = None
    valence: Optional[float] = None
    intensity: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    source: str
    statement_kind: str
    confidence: float
    entry_id: Optional[int] = None
    conversation_id: Optional[str] = None
    created_at: str


@app.get("/api/memories", response_model=list[MemoryResponse])
def list_memories(
    user: User = Depends(get_current_user),
    layer: Optional[str] = None,
    entry_id: Optional[int] = None,
    limit: int = 50,
) -> list[MemoryResponse]:
    """Return layered memories for the current user (session/event/stage/long_term)."""
    records = get_user_memories(
        user["username"],
        layer=layer,
        limit=max(1, min(limit, 200)),
        entry_id=entry_id,
    )
    return [
        MemoryResponse(
            id=r["id"],
            layer=r["layer"],
            content=r["content"],
            summary=r.get("summary"),
            emotion=r.get("emotion"),
            valence=r.get("valence"),
            intensity=r.get("intensity"),
            tags=r.get("tags") or [],
            themes=r.get("themes") or [],
            source=r["provenance"]["source"],
            statement_kind=r["provenance"]["statement_kind"],
            confidence=r["provenance"]["confidence"],
            entry_id=r.get("entry_id"),
            conversation_id=r.get("conversation_id"),
            created_at=r["provenance"]["created_at"],
        )
        for r in records
    ]


frontend_dir = PROJECT_ROOT / "UI" / "dist"
if (frontend_dir / "index.html").is_file():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# ── __main__ ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
