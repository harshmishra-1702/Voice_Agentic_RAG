"""
Token Server — FastAPI backend that mints LiveKit join tokens and serves
the frontend static files.

Keys (LIVEKIT_API_KEY, LIVEKIT_API_SECRET) are loaded from env vars on the
server side ONLY — they never reach the browser client.
"""

from __future__ import annotations

import json
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from livekit import api
from pydantic import BaseModel

app = FastAPI(title="VoiceOps Token Server")

# CORS — allow the frontend (served from same origin, but also dev servers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TokenRequest(BaseModel):
    """Request body for the token endpoint."""

    room_name: str = ""
    user_name: str = "sre-operator"


class TokenResponse(BaseModel):
    """Response with the scoped join token and LiveKit URL."""

    token: str
    url: str
    room_name: str


@app.post("/api/token", response_model=TokenResponse)
async def generate_token(req: TokenRequest) -> TokenResponse:
    """Mint a short-lived, scoped LiveKit join token.

    The token includes a RoomAgentDispatch so the VoiceOps agent is
    automatically dispatched when the room is created.
    """
    lk_url = os.environ.get("LIVEKIT_URL", "")
    lk_key = os.environ.get("LIVEKIT_API_KEY", "")
    lk_secret = os.environ.get("LIVEKIT_API_SECRET", "")

    if not all([lk_url, lk_key, lk_secret]):
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials not configured. Check .env file.",
        )

    # Generate a room name if not provided
    room_name = req.room_name or f"voiceops-{uuid.uuid4().hex[:8]}"
    participant_id = f"user-{uuid.uuid4().hex[:6]}"

    # Build agent dispatch config
    room_config = api.RoomConfiguration(
        agents=[
            api.RoomAgentDispatch(
                agent_name="voiceops",
                metadata=json.dumps({"user_name": req.user_name}),
            )
        ]
    )

    # Mint the token
    token = (
        api.AccessToken(api_key=lk_key, api_secret=lk_secret)
        .with_identity(participant_id)
        .with_name(req.user_name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(room_config)
        .to_jwt()
    )

    return TokenResponse(token=token, url=lk_url, room_name=room_name)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check endpoint for the stress test script."""
    return {"status": "ok", "service": "voiceops-token-server"}


# ── Serve frontend static files ─────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.isdir(FRONTEND_DIR):
    # Serve index.html at root
    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # Mount static files at root so relative paths in HTML (styles.css, app.js) work.
    # API routes registered above take precedence over this catch-all.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
