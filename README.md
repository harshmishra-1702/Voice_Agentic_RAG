# VoiceOps — Voice-Native SRE Runbook Copilot

A voice-first SRE copilot that lets engineers query runbooks and check server status entirely by voice, with hands-free interruption recovery and conversation continuity during tool work.

Built for the **DataForge × Pathway × Rime Hackathon**.

## Problem

An SRE with both hands inside a live server rack cannot type, tap, or read a screen. Voice isn't a convenience here — it's the only viable interface. This copilot lets them query dense internal runbooks and check system status mid-incident by speaking naturally, with the ability to interrupt and redirect without the agent finishing a stale response.

## Architecture

```
Browser (LiveKit web client, mic + speaker)
        |  WebRTC
LiveKit Cloud (media routing)
        |
Python Agent Worker (livekit-agents)
  ├─ VAD:  Silero (bundled default)
  ├─ STT:  Deepgram nova-3
  ├─ LLM:  Groq llama-3.3-70b-versatile (free tier, OpenAI-compatible)
  │         ├─ tool: query_runbook_rag(query) → ChromaDB semantic search
  │         └─ tool: check_server_status(host) → mocked async ping
  ├─ TTS:  Rime coda / astra (WebSocket streaming)
  ├─ Embeddings: local sentence-transformers (all-MiniLM-L6-v2)
  └─ Turn Fencing Layer (monotonic turn_id, staleness check, cancel-and-wait)
```

## Hard-Voice Feature

**Combined: Interruption/recovery + Conversation continuity during tool work**

- While a slow tool runs (3s RAG search), the agent speaks a filler phrase concurrently via Rime TTS.
- If the user interrupts mid-tool-call, queued Rime audio stops immediately, the stale tool result is dropped (never spoken or added to LLM context), and the new intent is processed cleanly.
- See [RIME_EVIDENCE.md](RIME_EVIDENCE.md) for the full claim, acceptance test, and runnable proof.

## Setup

### Prerequisites

- Python 3.11+
- A [LiveKit Cloud](https://cloud.livekit.io/) project (free tier works)
- API keys for: Rime, Deepgram, Groq (all free tier)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd V_RAG

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure credentials
copy .env.example .env
# Edit .env with your actual API keys
```

### Ingest Runbooks

```bash
python ingest.py
```

This reads the markdown files in `runbooks/`, chunks them, embeds them with a local sentence-transformer model (`all-MiniLM-L6-v2`, downloads automatically on first run), and stores them in a local ChromaDB instance.

### Run

```bash
# Terminal 1: Start the agent worker
python -m agent.main dev

# Terminal 2: Start the token server + frontend
uvicorn agent.token_server:app --port 8080
```

Open `http://localhost:8080` in your browser and click **Connect**.

### Run the Stress Test

```bash
python stress_test.py
```

## Third-Party Services

| Service | Purpose | Model / Config |
|---|---|---|
| **Rime** | Text-to-Speech | Model: `coda`, Speaker: `astra`, Language: `en-us`, Transport: WebSocket (`use_websocket=True`), Endpoint: `wss://users.rime.ai/v1/rime-tts`, Audio: PCM streamed |
| **Deepgram** | Speech-to-Text | Model: `nova-3`, Language: `en` |
| **Groq** | LLM (function calling) | Model: `llama-3.3-70b-versatile`, Free tier, OpenAI-compatible API |
| **sentence-transformers** | Embeddings (local) | Model: `all-MiniLM-L6-v2`, runs on-device, no API key |
| **LiveKit** | WebRTC media routing | Cloud or self-hosted SFU |
| **ChromaDB** | Vector store | Local persistent, cosine similarity |

## Known Limitations

1. **Not production RAG**: The runbook corpus is small (5 curated docs). This is intentional — the project proves fencing behavior, not RAG quality.
2. **Mocked server status**: `check_server_status` returns randomized mock data. It exists to prove multi-tool routing.
3. **Single-user sessions**: No auth, no session persistence, no multi-user support.
4. **English only**: No multilingual support.
5. **VAD sensitivity**: Very short utterances (<0.5s) may not trigger interruption. Rack ambient noise can cause false positives, mitigated by `resume_false_interruption`.

## Failure Behavior

- If a tool call fails, the agent speaks an explicit error message rather than going silent.
- If the Rime voice (`astra` on `coda`) is not available at startup, the agent refuses to boot and logs the available alternatives.
- If the LiveKit connection drops, the frontend shows a disconnection state.
- If the STT or LLM service is unreachable, the agent logs the error and attempts to inform the user vocally.

## Credential Hygiene

- All API keys live in `.env` (server-side only, loaded by the Python agent worker).
- `.env` is in `.gitignore` from the first commit.
- `.env.example` ships with placeholder values only.
- The browser client receives a short-lived LiveKit join token, never raw keys.
- Rime/STT/Groq keys never leave the backend process.

## Project Structure

```
├── .env.example          # Credential placeholders
├── .gitignore            # Excludes .env, chroma_db/
├── README.md             # This file
├── RIME_EVIDENCE.md      # Hard-voice claim + acceptance test
├── requirements.txt      # Python dependencies
├── ingest.py             # Runbook ingestion script
├── stress_test.py        # Programmatic acceptance test
│
├── agent/                # Python backend
│   ├── main.py           # AgentServer entrypoint
│   ├── voice_agent.py    # Agent + @function_tool definitions
│   ├── turn_fence.py     # Turn fencing state machine
│   ├── rag.py            # ChromaDB search
│   ├── preflight.py      # Rime voice validation
│   └── token_server.py   # FastAPI token endpoint
│
├── runbooks/             # SRE runbook content (5 files)
│
└── frontend/             # Browser client
    ├── index.html
    ├── styles.css
    └── app.js
```

## License

Built for the DataForge × Pathway × Rime Hackathon.
