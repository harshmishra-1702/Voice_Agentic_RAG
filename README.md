# VoiceOps — Voice-Native SRE Incident Runbook Copilot

### 📺 Demo Video: [Watch the Demo on Google Drive](https://drive.google.com/drive/folders/1GQSS7hS_7hS1L8v4ZnqKsxeVf-llKXtI)

[![Rime TTS](https://img.shields.io/badge/TTS-Rime%20(coda%2Fastra)-blueviolet)](https://rime.ai/)
[![LiveKit](https://img.shields.io/badge/Transport-LiveKit%20WebRTC-002B49)](https://livekit.io/)
[![Deepgram](https://img.shields.io/badge/STT-Deepgram%20nova--3-13EF93)](https://deepgram.com/)
[![License](https://img.shields.io/badge/Hackathon-DataForge%20%C3%97%20Pathway%20%C3%97%20Rime-orange)](https://dataforge.dev/)

> **VoiceOps** is a voice-native, full-duplex SRE copilot engineered for hands-busy datacenter and incident response scenarios. It enables on-call engineers to navigate complex operational runbooks, perform semantic knowledge retrieval, and diagnose server infrastructure entirely by voice — featuring seamless mid-utterance interruption recovery and conversational continuity during long-running tool operations.

---

## Table of Contents

- [Problem & Necessity of Voice](#problem--necessity-of-voice)
- [Hard Voice Engineering: Turn Fencing](#hard-voice-engineering-turn-fencing)
- [System Architecture](#system-architecture)
- [Exact Rime TTS Specification](#exact-rime-tts-specification)
- [Third-Party Services](#third-party-services)
- [Setup & Installation](#setup--installation)
- [Running the System](#running-the-system)
- [Verification & Acceptance Testing](#verification--acceptance-testing)
- [Known Limitations](#known-limitations)
- [Failure Behavior & Resilience](#failure-behavior--resilience)
- [Configuration & Credential Hygiene](#configuration--credential-hygiene)
- [Repository Structure](#repository-structure)

---

## Problem & Necessity of Voice

During high-severity infrastructure incidents, Site Reliability Engineers (SREs) frequently work in physically constrained environments:
- **Physical Datacenter Racks:** Both hands are occupied holding fiber optics, hot-swapping server power supplies, or checking patch cables inside dense server cages.
- **Cognitive & Screen Overload:** Multiple dashboards, metrics windows, and terminal sessions already saturate their visual field. Switching focus to a keyboard or documentation window adds dangerous latency and cognitive context-switching penalties.

In this situation, **voice is not a gimmick or convenience — it is the only viable operational interface**. A traditional chatbot with a text input or audio play button fails completely:
1. The operator cannot look away or type while holding live hardware.
2. If the assistant goes silent for 3–5 seconds during a database query, the operator cannot tell if the system crashed, the network dropped, or the query is running.
3. If an engineer spots a critical alert mid-sentence and yells an interruption, a standard agent talks over them, completing obsolete runbook steps and spewing outdated advice.

**VoiceOps solves both failure modes simultaneously** by coupling real-time bidirectional audio transport with an asynchronous **Turn Fencing Layer**.

---

## Hard Voice Engineering: Turn Fencing

The core innovation of VoiceOps addresses two combined hard-voice challenges from the challenge specification:
1. **Interruption & Recovery:** Instantly halts queued audio upon user speech onset, cancels in-flight background tool tasks, and drops obsolete responses before they can enter the conversational context.
2. **Conversation Continuity During Tool Work:** Concurrently streams low-latency verbal filler phrases via Rime TTS while tools execute in parallel, eliminating dead-air without introducing race conditions.

```
                  ┌──────────────────────────────────────────────┐
                  │             USER SPEAKS TURN N               │
                  │   "Search outage runbooks for switch failure"│
                  └──────────────────────┬───────────────────────┘
                                         │
                        [Increment turn_id = N (e.g. 1)]
                                         │
                   ┌─────────────────────┴──────────────────────┐
                   │                                            │
        (Concurrent Non-Blocking)                    (Asynchronous Tool Task)
                   │                                            │
                   ▼                                            ▼
      Rime TTS Streams Filler                      ChromaDB Semantic Search
   "Searching the outage runbooks..."                    (3.0s delay)
                   │                                            │
                   │    ⚡ USER INTERRUPTS AT T = 1.0s           │
                   │    "Actually, check rack-14 instead!"      │
                   │                                            │
                   ▼                                            │
      LiveKit VAD detects speech                                │
      - Cut queued Rime audio stream                            │
      - Advance turn_id = N + 1 (2)                             │
      - cancel_and_wait(Task_Turn_1)                            │
                   │                                            │
                   ▼                                            │
      Turn 2 tool dispatched                                    │
      check_server_status("rack-14")                            ▼
                   │                               Tool Turn 1 Resolves
                   │                               Staleness Check:
                   │                               dispatch_turn_id (1) < current_turn_id (2)
                   ▼                                            │
      Turn 2 completes and speaks                               ▼
      "Server rack-14 status: healthy."            ❌ DROPPED & LOGGED AS STALE
                                                   (Never spoken, never in LLM context)
```

### Key Technical Mechanisms (`agent/turn_fence.py`)
- **Monotonic Turn State:** A single source-of-truth integer `turn_id` tracks active conversation turns.
- **Dual Staleness Checks:** Staleness is checked at tool dispatch **and** at the critical moment right before speech generation, closing the microscopic race window where a tool resolves just as user speech begins.
- **Cancel-and-Wait Task Reaper:** Cancels Python `asyncio.Task` handles and awaits clean shutdown, freeing system resources.
- **Zero Double-Speaking:** Prevents overlapping audio streams; only the active turn's audio reaches the audio output buffer.

---

## System Architecture

VoiceOps connects a browser client to a Python-based intelligent agent worker via WebRTC, orchestrated by LiveKit and powered by Rime TTS:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER INTERFACE                        │
│   WebRTC Audio Stream (Mic/Speaker) + LiveKit DataChannel Telemetry     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ WebRTC
┌───────────────────────────────────▼────────────────────────────────────┐
│                    LIVEKIT SFU (CLOUD / ON-PREMISE)                    │
│             Real-Time Media Routing & Bidirectional Transport          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ WebRTC / IPC
┌───────────────────────────────────▼────────────────────────────────────┐
│                  VOICEOPS AGENT WORKER (Python 3.11+)                  │
│                                                                        │
│   ├─ VAD: Silero VAD (Frame-level Voice Activity Detection)            │
│   ├─ STT: Deepgram nova-3 (Conversational speech-to-text)              │
│   ├─ LLM: OpenRouter / Groq (Fast OpenAI-compatible function calling)  │
│   ├─ TTS: Rime TTS (`coda` / `astra`, WebSocket streamed PCM)          │
│   │                                                                    │
│   ├─ TURN FENCING LAYER (Core Innovation):                             │
│   │    • Monotonic turn_id state machine                               │
│   │    • Dual-point staleness verification                             │
│   │    • Concurrent filler streaming without awaiting                  │
│   │    • Cancel-and-wait asynchronous task reaper                      │
│   │                                                                    │
│   └─ AGENTIC TOOLS:                                                    │
│        • query_runbook_rag: ChromaDB semantic search + all-MiniLM-L6-v2 │
│        • check_server_status: Real-time asynchronous infrastructure probe│
│        • search_the_web: Live Tavily API internet retrieval            │
│        • read_website_content: Jina AI URL reader                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Exact Rime TTS Specification

To ensure 100% compliance with challenge specifications, Rime TTS is integrated as the primary, default speech generation system with the following configuration:

| Parameter | Shipped Production Value | Technical Description |
|---|---|---|
| **Model ID** | `coda` | Rime's flagship conversational text-to-speech model, optimized for natural human cadence, low latency, and realistic technical delivery. |
| **Speaker** | `astra` | Clear, professional, authoritative English voice tested for optimal intelligibility in noisy environments. |
| **Language** | `en-us` | Standard US English dialect configuration. |
| **Endpoint** | `wss://users.rime.ai/v1/rime-tts` | Dedicated WebSocket endpoint provided by `livekit-plugins-rime`. |
| **Audio Format** | Linear PCM (16-bit signed, 24kHz, mono) | Low-overhead, uncompressed streaming PCM audio for instantaneous decoding and zero-transcoding playback. |
| **Transport** | WebSocket (`use_websocket=True`) | Bidirectional streaming transport enabling incremental chunk delivery and sub-300ms time-to-first-audio. |
| **Timestamps** | Word-Level Timestamps | Enabled via the WebSocket transport, allowing frame-accurate truncation of speech mid-word upon interruption. |
| **Preflight Verification** | Automated Live Catalog Check | Pre-boot validator (`agent/preflight.py`) queries `https://users.rime.ai/data/voices/all-v2.json` to confirm `astra` availability under `coda`. |

---

## Third-Party Services

| Service | Purpose | Model / Engine | Protocol / Transport | Auth & Secret Handling |
|---|---|---|---|---|
| **Rime** | Spoken Speech Synthesis (Primary) | Model: `coda`<br>Speaker: `astra` | WebSocket (`wss://`) | `RIME_API_KEY` loaded server-side only; never leaked to client. |
| **Deepgram** | Speech-to-Text Transcription | Model: `nova-3`<br>Lang: `en` | Streaming WebSocket | `DEEPGRAM_API_KEY` stored in `.env`. |
| **OpenRouter / Groq** | LLM Orchestration & Tool Calling | Nemotron-3.5-lightning / Qwen-3.6-27B / Llama 3 | HTTPS REST (Streaming SSE) | `OPENROUTER_API_KEY` or `GROQ_API_KEY` on backend. |
| **LiveKit** | WebRTC Media Routing & DataChannel | Cloud SFU / Self-hosted | WebRTC (SRTP/UDP) | Short-lived scoped JWT join tokens generated by `token_server.py`. |
| **Tavily** | Live Web Search | Search API | HTTPS POST | `TAVILY_API_KEY` server-side secret. |
| **Jina AI** | Webpage Content Extraction | Reader API (`r.jina.ai`) | HTTPS GET | `JINA_API_KEY` optional bearer token. |
| **ChromaDB** | Semantic Runbook Vector Store | Local persistent database | Embedded Python engine | Local file storage (`chroma_db/`); no network keys required. |
| **Sentence Transformers** | Runbook Embeddings | `all-MiniLM-L6-v2` | Local on-device inference | 100% offline, local compute; no external API. |

---

## Setup & Installation

### 1. Prerequisites
- **Python:** 3.11 or higher
- **Node.js:** Not required (frontend is vanilla JS/HTML)
- **LiveKit Cloud Account:** Free tier at [cloud.livekit.io](https://cloud.livekit.io/)
- **API Keys:** Rime API Key, Deepgram API Key, OpenRouter or Groq API Key

### 2. Clone and Setup Environment
```bash
# Clone repository
git clone https://github.com/your-username/Voice_Agentic_RAG.git
cd Voice_Agentic_RAG

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux / macOS:
source venv/bin/activate

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Credentials
Copy the placeholder configuration and insert your API keys:
```bash
# On Windows:
copy .env.example .env

# On Linux / macOS:
cp .env.example .env
```
Edit `.env` with your editor of choice. (See [Configuration Hygiene](#configuration--credential-hygiene) below.)

### 4. Run Knowledge Ingestion
Populate ChromaDB with the curated SRE operational runbooks:
```bash
python ingest.py
```
*Note: This downloads `all-MiniLM-L6-v2` on first run and embeds documents locally.*

---

## Running the System

Running VoiceOps requires two lightweight backend processes:

### Terminal 1: LiveKit Agent Worker
Starts the voice agent worker, executes the Rime preflight check, and listens for room connections:
```bash
python -m agent.main dev
```

### Terminal 2: Token Server & Web Client
Starts the FastAPI server that generates secure participant tokens and hosts the browser UI:
```bash
uvicorn agent.token_server:app --port 8000 --reload
```

### Accessing the UI
1. Navigate to `http://localhost:8000` in Google Chrome or Microsoft Edge.
2. Click **Connect** to initialize the WebRTC audio session.
3. Once the agent announces `"VoiceOps online. What do you need?"`, you can begin speaking.

---

## Verification & Acceptance Testing

VoiceOps includes automated verification scripts to validate the Rime integration and prove turn fencing behavior without manual voice timing:

### 1. Rime Voice Catalog Preflight Check
Verify that the exact model (`coda`) and voice (`astra`) are live in Rime's production catalog:
```bash
# Standalone CLI preflight check
python -m agent.preflight

# Or run the comprehensive unit test suite (9 tests covering all catalog schemas)
python tests/test_preflight.py
```
*Expected output: `[Preflight] SUCCESS: Rime voice 'astra' is verified under model 'coda'.`*

### 2. Automated Interruption Stress Test
The stress harness (`stress_test.py`) connects as a synthetic LiveKit participant, dispatches a slow RAG query, injects an interruption at exactly 1.0s, and asserts that stale results are dropped:
```bash
# Terminal 3: Execute the stress test
python stress_test.py
```
The script validates all 5 core assertions and generates `stress_test_result.json`. See [RIME_EVIDENCE.md](RIME_EVIDENCE.md) for full evidence details.

---

## Known Limitations

In accordance with hackathon guidelines, we disclose all known architectural constraints:
1. **VAD Endpointing Threshold:** Very brief utterances (<0.5 seconds) such as coughs or background murmurs may not trip turn advance. The VAD endpointing delay is tuned to `0.5s` to prevent false interruptions from datacenter fan noise.
2. **Asyncio Cancellation Boundaries:** Task cancellation via `asyncio.Task.cancel()` is best-effort in Python; it interrupts tasks at await boundaries (such as network calls or sleeps), but cannot interrupt blocking CPU-bound C extensions mid-instruction.
3. **Single Tool Concurrency per Turn:** The fencing layer currently tracks one active tool execution per conversational turn. Parallel branch-and-join tool calls within a single turn are queued sequentially.
4. **Network Jitter:** In high-packet-loss mobile environments, WebRTC audio packets may experience jitter; however, Rime's WebSocket connection to the agent worker remains stable in server-to-server cloud infrastructure.

---

## Failure Behavior & Resilience

VoiceOps handles partial failures gracefully across every subsystem:

| Failure Mode | Agent Detection | User Experience | Recovery Action |
|---|---|---|---|
| **Rime Catalog Drift / Missing Voice** | `agent/preflight.py` checks voice catalog on startup. | Agent fails fast during boot with clear diagnostics instead of failing silently during a live call. | Operator is alerted to select another voice in `.env`. |
| **Tool Execution Error** | `try/except` block inside `@function_tool`. | The agent vocally explains the error (e.g., *"I'm sorry, the runbook search failed: connection timeout"*) rather than remaining silent. | Session remains live; user can retry. |
| **Stale Result on Interruption** | `turn_fence.is_stale()` evaluates `True`. | The stale result is silently discarded; no overlapping speech or obsolete context occurs. | Discard event emitted to UI; new turn proceeds. |
| **LiveKit Disconnection** | Frontend WebRTC state listener. | UI badge turns red and displays *"Disconnected"*. | Browser client attempts exponential backoff reconnection. |
| **STT / LLM Rate Limit** | Provider exception handler in LiveKit runtime. | Agent logs diagnostic error and provides polite fallback prompt. | Token server / agent worker preserves session state. |

---

## Configuration & Credential Hygiene

VoiceOps enforces strict credential security:
- **Server-Side Isolation:** All API credentials (`RIME_API_KEY`, `DEEPGRAM_API_KEY`, `LIVEKIT_API_KEY`, etc.) are loaded into memory exclusively by the Python backend.
- **Zero Client Leakage:** The browser frontend never touches third-party API keys. It receives only a short-lived, cryptographically signed LiveKit JWT minted by `token_server.py`.
- **Git Hygiene:** `.env` and `chroma_db/` are strictly ignored by `.gitignore`. Only `.env.example` containing non-secret placeholder variables is committed.
- **Preflight Verification:** Passes organizer secret preflight and Rime catalog schema validation.

---

## Repository Structure

```
Voice_Agentic_RAG/
│
├── README.md                 # Project documentation & operational runbook
├── RIME_EVIDENCE.md          # Hard-voice claim, acceptance test & proof
├── .env.example              # Environment template with placeholders only
├── .gitignore                # Protects secrets, databases, and logs
├── requirements.txt          # Python package dependencies
│
├── stress_test.py            # Automated programmatic acceptance test
├── ingest.py                 # Markdown runbook chunker & ChromaDB embedder
│
├── agent/                    # Python Backend Worker
│   ├── main.py               # LiveKit AgentServer entrypoint & event wiring
│   ├── voice_agent.py        # VoiceOpsAgent class & tool definitions
│   ├── turn_fence.py         # Turn fencing state machine & task reaper
│   ├── rag.py                # ChromaDB vector retrieval engine
│   ├── preflight.py          # Rime live voice catalog validator
│   ├── providers.py          # STT/LLM/TTS pluggable provider adapters
│   └── token_server.py       # FastAPI backend for tokens & static UI
│
├── tests/                    # Verification & Unit Tests
│   ├── test_preflight.py     # 9 unit tests for catalog parsing & validation
│   ├── test_api.py           # Token server health & endpoint tests
│   └── test_education.py     # Tool & experiment logic tests
│
├── runbooks/                 # Curated SRE operational runbooks (Markdown)
│   └── .gitkeep
│
└── frontend/                 # Browser Web Client
    ├── index.html            # Single-page operations dashboard
    ├── styles.css            # Dark-theme SRE console styling
    └── app.js                # LiveKit WebRTC client & DataChannel listeners
```

---

## Challenge Summary

Built for the **DataForge × Pathway × Rime Hackathon**. VoiceOps demonstrates that by treating full-duplex conversational fencing and audio truncation as first-class architectural primitives, voice interfaces can be reliably deployed in mission-critical, high-stress engineering environments.
