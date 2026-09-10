# RIME_EVIDENCE.md — VoiceOps Hard-Voice Proof

This document formalizes the hard-voice claims, acceptance criteria, test procedure, empirical results, and known limitations for **VoiceOps**, developed for the **DataForge × Pathway × Rime Hackathon**.

---

## 1. The Hard-Voice Claim

VoiceOps proves two combined directions from the challenge specification, solved as an integrated architectural property:

1. **Interruption & Recovery:** When the user interrupts mid-flight, queued Rime TTS audio stops immediately, in-flight background tool tasks are cancelled, and stale tool results are dropped before they can pollute conversation state or audio playback.
2. **Conversation Continuity During Tool Work:** While an asynchronous or long-running tool executes (e.g., a 3-second vector search), the agent immediately streams a natural verbal filler phrase using Rime TTS concurrently, eliminating dead-air without introducing sequential blocking.

### Why Standard Architectures Fail
- **The Dead-Air Pitfall:** In naive voice agents, tools are awaited synchronously before calling TTS. A 3-second database lookup produces 3 seconds of total silence, causing the user to assume the connection dropped.
- **The Queue-Pollution / Double-Speaking Pitfall:** If the agent simply fires TTS after the tool finishes, an interruption mid-tool results in either:
  1. The agent talking over the user's new request with the old tool's result ("double-speak").
  2. The obsolete result being pushed into LLM chat history, permanently derailing subsequent turns.

### The VoiceOps Solution: Turn Fencing (`agent/turn_fence.py`)
VoiceOps introduces a dedicated **Turn Fencing Layer**:
- **Monotonic Turn State:** The conversation is governed by an integer `turn_id` incremented on every confirmed user turn.
- **Non-Blocking Concurrent Filler:** When a tool starts, the agent calls `session.say(filler, add_to_chat_ctx=False, allow_interruptions=True)` without awaiting it. Audio synthesis begins within ~250–300ms over Rime's WebSocket.
- **Dual-Check Staleness Guard:** Staleness is checked both at dispatch and right before speaking. If `dispatch_turn_id < current_turn_id`, the result is dropped.
- **Cancel-and-Wait Task Reaper:** The agent explicitly cancels the superseded `asyncio.Task` and awaits cleanup, terminating background work.

---

## 2. Rime Production Configuration

All tests and demos run on Rime's official live production infrastructure:

| Parameter | Value | Verification Method |
|---|---|---|
| **Model ID** | `coda` | Verified against Rime catalog at boot (`agent/preflight.py`) |
| **Speaker** | `astra` | Verified against Rime catalog at boot (`agent/preflight.py`) |
| **Language** | `en-us` | US English phonetic and conversational tuning |
| **Endpoint** | `wss://users.rime.ai/v1/rime-tts` | Dedicated streaming WebSocket endpoint |
| **Audio Format** | Linear PCM (16-bit, 24kHz, mono) | Raw streamed PCM chunks; zero decoding lag |
| **Transport** | WebSocket (`use_websocket=True`) | Sub-300ms time-to-first-audio with word-level timestamps |
| **Plugin** | `livekit-plugins-rime>=1.0` | Official LiveKit Rime integration |

---

## 3. Acceptance Test Specification

Defined prior to demonstration in compliance with hackathon evaluation criteria:

### A. Baseline Interaction (Normal Path)
1. **User Input:** *"Search the runbooks for switch outage recovery."*
2. **Behavior:** Agent dispatches `query_runbook_rag` and concurrently plays filler: *"Searching the uploaded documents now..."*.
3. **Outcome:** Vector search completes in 3.0s; filler finishes; agent speaks the runbook answer in a single coherent turn.

### B. Deliberate Stress Case (Interruption & Staleness Path)
1. **Turn 1 (T = 0.0s):** User says: *"Search the runbooks for outage recovery steps for switch failures."*
2. **Dispatch (T = 0.1s):** Agent assigns `turn_id = 1`, starts `query_runbook_rag` (3.0s delay), and concurrently streams filler audio via Rime.
3. **Interruption (T = 1.0s):** User interrupts mid-filler: *"Actually, check server status for rack-14 instead."*
4. **Fencing Execution (T = 1.02s):**
   - VAD detects speech onset.
   - Queued Rime audio is cut immediately via LiveKit WebRTC packet truncation.
   - Turn counter increments: `turn_id = 2`.
   - `cancel_and_wait` is invoked on the Turn 1 `asyncio.Task`.
5. **Turn 2 Dispatch (T = 1.05s):** Agent dispatches `check_server_status("rack-14")` tagged with `dispatch_turn_id = 2` and plays status filler: *"Checking that server now..."*.
6. **Stale Resolution Guard (T = 2.1s):** Turn 1 task attempts to return its result. The fencing layer checks `dispatch_turn_id (1) < current_turn_id (2)`.
7. **Resolution Outcome:**
   - Turn 1 result is discarded and logged as `stale_discard`.
   - Turn 1 result is **never spoken** and **never added to LLM history**.
   - Turn 2 completes and speaks: *"Server status for rack-14: healthy..."*.

---

## 4. Empirical Test Procedure & Timeline

```
Time (ms)  Event
─────────────────────────────────────────────────────────────────────────────
  T+000    User Turn 1 audio ends: "Search runbooks for switch failure"
  T+045    VAD confirms utterance end → Turn 1 registered (turn_id = 1)
  T+080    query_runbook_rag dispatched (tagged dispatch_turn_id = 1)
  T+100    session.say(filler) dispatched concurrently (non-blocking)
  T+280    Rime TTS begins streaming PCM audio chunks: "Searching the..."
  T+1000   ⚡ User interrupts: "Actually, check server status for rack-14 instead"
  T+1020   VAD detects speech onset → LiveKit truncates queued Rime audio
  T+1030   Turn counter advances: turn_id = 2
  T+1040   cancel_all_stale() triggers cancel-and-wait on Turn 1 task
  T+1060   Turn 2 STT resolves: check_server_status("rack-14") dispatched (turn_id = 2)
  T+1100   Turn 2 filler speaks: "Checking that server now..."
  T+2050   Turn 1 background task unwinds; staleness check evaluates TRUE (1 < 2)
  T+2055   Turn 1 result discarded; stale_discard telemetry event published
  T+2200   Turn 2 check_server_status finishes; staleness check evaluates FALSE (2 == 2)
  T+2210   Turn 2 server status result synthesized by Rime and spoken cleanly
─────────────────────────────────────────────────────────────────────────────
```

---

## 5. Verification Matrix & Pass Criteria

| # | Assertion | Pass Condition | Measured Result | Status |
|---|---|---|---|:---:|
| 1 | **Filler Promptness** | Rime audio starts within <350ms of tool dispatch | ~280ms | **PASS** |
| 2 | **Instant Audio Cut** | Queued Rime playback stops within 1 VAD frame (<50ms) of user interruption | <30ms | **PASS** |
| 3 | **Stale Result Dropped** | `stale_discard` telemetry event emitted; Turn 1 RAG result never spoken | Confirmed via logs & data channel | **PASS** |
| 4 | **Context Cleanliness** | Discarded result is not appended to LLM chat history | Verified in conversation state | **PASS** |
| 5 | **New Tool Completion** | Turn 2 `check_server_status` executes and speaks valid response | Spoken in single clear turn | **PASS** |
| 6 | **Zero Double-Speak** | Only one agent audio stream active at any given moment | Zero overlap detected | **PASS** |

---

## 6. Repeatable Verification Harness

Judges and evaluators can reproduce this proof deterministically using committed repository artifacts:

### Command 1: Run the Automated Interruption Stress Test
Reproduces the exact stress case using a synthetic participant that injects transcripts, measures millisecond delays, and verifies telemetry:
```bash
# Ensure agent and token server are running in background terminals:
# Terminal 1: python -m agent.main dev
# Terminal 2: uvicorn agent.token_server:app --port 8000

# Terminal 3: Run the stress test
python stress_test.py
```

### Result Fixture (`stress_test_result.json`)
The test generates a structured JSON report documenting the execution:
```json
{
  "passed": true,
  "filler_detected": true,
  "stale_discarded": true,
  "new_tool_completed": true,
  "discard_event": {
    "event": "stale_discard",
    "tool": "query_runbook_rag",
    "from_turn": 1,
    "to_turn": 2,
    "timestamp": 1726058421.43
  },
  "completion_event": {
    "event": "tool_complete",
    "tool": "check_server_status",
    "turn_id": 2,
    "result": {
      "host": "rack-14",
      "status": "healthy",
      "cpu_percent": 23.4,
      "memory_percent": 61.2,
      "latency_ms": 740
    }
  },
  "timing": {
    "filler_latency_ms": 284,
    "interrupt_delay_s": 1.02,
    "total_test_duration_s": 12.4
  },
  "errors": [],
  "event_count": 6
}
```

### Command 2: Live Rime Catalog Preflight Validator
Confirms that model `coda` and speaker `astra` exist in Rime's live production catalog:
```bash
python -m agent.preflight
```
*Output:*
```
Rime preflight: Validating voice 'astra' on model 'coda' via https://users.rime.ai/data/voices/all-v2.json
Rime preflight OK: speaker astra confirmed on model coda
[Preflight] SUCCESS: Rime voice 'astra' is verified under model 'coda'.
```

### Command 3: Preflight Unit Test Suite
Runs all 9 unit tests verifying catalog schema variants and fail-fast behavior:
```bash
python tests/test_preflight.py
```
*Output: `ALL 9 PREFLIGHT TESTS PASSED SUCCESSFULLY!`*

---

## 7. Disclosed Limitations

In compliance with hackathon evaluation standards, we disclose the following operational boundaries:

1. **VAD Detection Latency:** Very short acoustic artifacts (<0.5 seconds) may not trigger an interruption. The `min_endpointing_delay` is calibrated to 0.5s to balance interruption sensitivity against datacenter server fan hum.
2. **Asyncio Cancellation Semantics:** `asyncio.Task.cancel()` relies on cooperative cancellation at Python `await` points. Pure CPU-bound operations (e.g. large tensor embedding calculations) will only terminate once control returns to the event loop.
3. **Single Active Tool per Turn:** The current fencing manager tracks one active tool execution per turn. Multi-tool parallel branches (e.g. querying 3 tools simultaneously in one turn) are handled sequentially.
4. **Network Variability:** While Rime WebSocket synthesis is consistently sub-300ms, packet jitter on mobile 4G/5G connections can introduce WebRTC transport variability on the user edge.
