# RIME_EVIDENCE.md — VoiceOps Hard-Voice Claim

## Claim

VoiceOps proves two combined hard-voice directions from the DataForge × Pathway × Rime challenge brief:

1. **Interruption and recovery** — when the user speaks mid-tool-call, queued Rime audio stops immediately, the stale tool result is dropped, and the new user intent is processed cleanly.
2. **Conversation continuity during tool work** — while a slow tool (3-second RAG search) runs, the agent speaks a filler phrase via Rime TTS concurrently, maintaining the conversational flow without a dead-air gap.

These are combined into a single fencing mechanism, not treated as separate features.

## Rime Integration Details

| Parameter | Value |
|---|---|
| Plugin | `livekit-plugins-rime` |
| Model | `coda` |
| Speaker | `astra` |
| Language | `en-us` |
| Transport | WebSocket (`use_websocket=True`) |
| Audio format | PCM, streamed via WebSocket |
| Endpoint | `wss://users.rime.ai/v1/rime-tts` (auto-detected by plugin) |
| Word-level timestamps | Enabled (via WebSocket streaming) |

### Voice Validation

At startup, the agent runs an automated preflight check (`agent/preflight.py`):
1. Fetches Rime's live voice catalog from `https://users.rime.ai/data/voices/all-v2.json`
2. Asserts `astra` is present under the `coda` model
3. Logs the result — visible in the agent's startup output and demo recording
4. If the voice is missing, the agent refuses to boot (fail-fast, not fail-silent)

## Acceptance Test

### Procedure

1. User says: **"Search the runbooks for outage recovery steps for switch failures."**
2. The agent dispatches `query_runbook_rag` (tagged with `turn_id=N`).
3. Concurrently, the agent speaks a Rime filler phrase ("Scanning the outage runbooks now…") via `session.say(filler, add_to_chat_ctx=False)` — the filler runs in parallel with the tool, not sequentially.
4. The 3-second simulated RAG delay begins.
5. **At ~1.0 seconds** (mid-filler or mid-delay), the user interrupts: **"Actually, check server status for rack-14 instead."**
6. The turn fencing mechanism:
   - Advances `turn_id` to `N+1`
   - Cancels the in-flight RAG `asyncio.Task` via `cancel_and_wait`
   - LiveKit's default behavior stops queued Rime audio (we don't fight this)
7. The new tool `check_server_status("rack-14")` dispatches at `turn_id=N+1`.
8. When the stale RAG task resolves (~2 seconds later, despite cancellation attempt), the fencing layer's `is_stale()` check catches it and drops the result.

### Expected Results

| Assertion | Pass Condition |
|---|---|
| Filler begins promptly | Rime audio starts within ~300ms of tool dispatch |
| Queued audio stops on interrupt | Agent speech stops within one VAD frame of user speech onset |
| Stale RAG result dropped | `stale_discard` event logged; result never spoken or added to LLM context |
| New tool completes | `check_server_status` result spoken as single non-overlapping turn |
| No double-speak | Only one agent voice stream active at any time |

### Runnable Script

```bash
# Terminal 1: Start the agent worker
python -m agent.main dev

# Terminal 2: Start the token server
uvicorn agent.token_server:app --port 8080

# Terminal 3: Run the stress test
python stress_test.py
```

The stress test (`stress_test.py`) reproduces this exact sequence programmatically:
- Connects as a synthetic LiveKit participant
- Injects the first query via data channel
- Waits exactly 1.0 second
- Injects the interrupting query
- Waits for resolution
- Asserts all conditions above via data channel events
- Writes detailed results to `stress_test_result.json`

### Result Format

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
    "to_turn": 2
  },
  "timing": {
    "interrupt_delay_s": 1.02,
    "total_test_duration_s": 15.3
  },
  "errors": []
}
```

## Limitations

1. **VAD threshold**: Very short utterances (< 0.5s) may not trigger interruption. The `min_endpointing_delay` is set to 0.5s to balance responsiveness against false positives from rack ambient noise.
2. **Cancellation is best-effort**: `asyncio.Task.cancel()` sets a flag but doesn't guarantee immediate stop if the coroutine is blocked in a non-async call. The simulated delay uses `asyncio.sleep()` which is cancellable, but a real database query might not be.
3. **False interruption recovery**: Relies on LiveKit's `resume_false_interruption` setting. Effectiveness depends on the VAD model's accuracy with the user's specific ambient noise profile.
4. **Network jitter**: WebRTC and WebSocket latencies can vary. The 300ms filler target is measured from dispatch time on the server, not from the user's perspective.
5. **Single concurrent tool**: The current fencing model tracks one active tool per turn. Parallel tool calls within a single turn are not supported (not needed for this use case).

## Architecture Reference

See [architecture.md](architecture.md) for the full component diagram and race-condition analysis.
