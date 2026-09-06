"""
Token Server — FastAPI backend that mints LiveKit join tokens and serves
the frontend static files.

Keys (LIVEKIT_API_KEY, LIVEKIT_API_SECRET) are loaded from env vars on the
server side ONLY — they never reach the browser client.
"""

from __future__ import annotations

import json
import os
import sys
import uuid

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv

# Explicitly load .env from project root, then fall back to cwd
load_dotenv(os.path.join(root_dir, ".env"))
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from livekit import api
from pydantic import BaseModel
import shutil
import subprocess

try:
    import ingest
    import threading
    # Preload the heavy PyTorch model and ChromaDB into memory in a background thread 
    # the moment the server starts, so uploads are instantly fast.
    threading.Thread(target=ingest.get_collection, daemon=True).start()
except Exception as e:
    print("Warning: Could not preload ingestion models:", e)

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


class ExperimentRequest(BaseModel):
    sequence: list[str]
    memory_size: int = 8
    update_strength: float = 0.6
    interference: float = 0.1
    seed: int = 42
    retrieval_targets: list[str] | None = None

@app.post("/api/v1/experiment/memory/run")
async def run_memory_experiment_api(req: ExperimentRequest):
    from agent.education.experiment_engine import run_experiment
    return run_experiment(
        sequence=req.sequence,
        memory_size=req.memory_size,
        update_strength=req.update_strength,
        interference=req.interference,
        seed=req.seed,
        retrieval_targets=req.retrieval_targets
    )

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
@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for the stress test script."""
    return {"status": "ok", "service": "voiceops-token-server"}


@app.post("/api/ingest")
async def ingest_file(file: UploadFile = File(...)):
    """Upload a file to the runbooks directory and trigger ingestion."""
    import asyncio
    
    runbooks_dir = os.path.join(root_dir, "runbooks")
    os.makedirs(runbooks_dir, exist_ok=True)
    
    file_path = os.path.join(runbooks_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Run in thread to not block FastAPI event loop
        await asyncio.to_thread(ingest.ingest, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
        
    return {"status": "success", "filename": file.filename}


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
