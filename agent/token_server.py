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

from typing import Any

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from livekit import api
from pydantic import BaseModel
import shutil
import subprocess
import sys

root_dir = os.path.dirname(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

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


@app.get("/api/documents")
async def list_documents() -> list[dict[str, Any]]:
    """List all runbook files in the runbooks directory with their chunk counts."""
    runbooks_dir = os.path.join(root_dir, "runbooks")
    if not os.path.exists(runbooks_dir):
        return []

    # Get chunk counts from ChromaDB
    chunk_counts: dict[str, int] = {}
    try:
        col = ingest.get_collection()
        res = col.get(include=["metadatas"])
        for meta in res.get("metadatas", []):
            if meta and "source" in meta:
                src = meta["source"]
                chunk_counts[src] = chunk_counts.get(src, 0) + 1
    except Exception as e:
        print("Warning: could not query collection chunks:", e)

    results = []
    valid_exts = (".md", ".txt", ".pdf", ".docx", ".pptx")
    for f in sorted(os.listdir(runbooks_dir)):
        if f.startswith(".") or not f.lower().endswith(valid_exts):
            continue
        fp = os.path.join(runbooks_dir, f)
        stat = os.stat(fp)
        results.append({
            "filename": f,
            "size_bytes": stat.st_size,
            "modified_at": int(stat.st_mtime),
            "chunks_count": chunk_counts.get(f, 0)
        })
    return results


@app.delete("/api/documents/{filename}")
async def delete_document(filename: str) -> dict[str, Any]:
    """Delete a document from disk and purge its vector embeddings from ChromaDB."""
    runbooks_dir = os.path.join(root_dir, "runbooks")
    file_path = os.path.join(runbooks_dir, filename)

    deleted_from_disk = False
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
            deleted_from_disk = True
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file from disk: {e}")

    deleted_chunks = 0
    try:
        col = ingest.get_collection()
        res = col.get(where={"source": filename})
        chunk_ids = res.get("ids", [])
        if chunk_ids:
            col.delete(ids=chunk_ids)
            deleted_chunks = len(chunk_ids)
    except Exception as e:
        print(f"Warning: could not delete chunks for {filename} from ChromaDB: {e}")

    return {
        "status": "deleted",
        "filename": filename,
        "deleted_from_disk": deleted_from_disk,
        "deleted_chunks": deleted_chunks
    }


@app.get("/api/system/stats")
async def system_stats() -> dict[str, Any]:
    """Return runtime telemetry, ChromaDB status, and system metrics."""
    total_chunks = 0
    try:
        col = ingest.get_collection()
        total_chunks = col.count()
    except Exception:
        pass

    runbooks_dir = os.path.join(root_dir, "runbooks")
    doc_count = 0
    if os.path.exists(runbooks_dir):
        doc_count = len([f for f in os.listdir(runbooks_dir) if not f.startswith(".")])

    return {
        "status": "operational",
        "service": "VoiceOps SRE Copilot",
        "total_chunks": total_chunks,
        "documents_count": doc_count,
        "embedding_model": "all-MiniLM-L6-v2 (Local)",
        "tts_provider": "Rime coda / astra (WebSocket)",
        "stt_provider": "Deepgram nova-3",
        "llm_model": "openai/gpt-oss-20b (Groq)",
        "turn_fencing": "Monotonic Turn ID & Async Cancel-and-Wait",
        "webrtc": "LiveKit SFU"
    }


@app.post("/api/simulate")
async def simulate_event(data: dict[str, Any]) -> dict[str, Any]:
    """Helper simulation endpoint for interactive UI testing and live judge presentations."""
    action = data.get("action", "ping")
    if action == "check_server":
        host = data.get("host", "prod-db-01")
        return {
            "event": "tool_complete",
            "tool": "check_server_status",
            "host": host,
            "status": "healthy",
            "cpu_percent": 34.8,
            "memory_percent": 68.2,
            "uptime": "21d 4h 12m",
            "latency_ms": 14,
            "message": f"Server status for {host}: healthy. CPU at 34.8%, memory at 68.2%, uptime 21d 4h 12m, latency 14ms."
        }
    elif action == "query_runbook":
        query = data.get("query", "high latency spike recovery")
        return {
            "event": "tool_complete",
            "tool": "query_runbook_rag",
            "query": query,
            "result_count": 2,
            "message": f"Found 2 relevant runbook sections for '{query}'. Citing Agrim___Resume.pdf / SRE incident playbook: automated rollback triggers on p99 > 850ms."
        }
    elif action == "barge_in":
        return {
            "event": "stale_discard",
            "tool": "query_runbook_rag",
            "from_turn": 3,
            "to_turn": 4,
            "message": "⚠ Barge-in detected: stale tool result discarded (turn 3 → turn 4)"
        }
    return {"status": "ok"}


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
