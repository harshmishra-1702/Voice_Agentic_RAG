# Architecture — VoiceOps

## Components

```
Browser (LiveKit web client, mic + speaker)
        |  WebRTC
LiveKit Cloud / self-hosted SFU (media routing only)
        |
Python Agent Worker (livekit-agents)
  ├─ VAD:  Silero (bundled default) — turn/interruption detection
  ├─ STT:  Deepgram nova-3 (or AssemblyAI if reusing existing familiarity)
  ├─ LLM:  gpt-4o-mini via livekit-plugins-openai (function calling)
  │         ├─ tool: query_runbook_rag(query) -> ChromaDB search (3s delay)
  │         └─ tool: check_server_status(host) -> mocked async ping
  ├─ TTS:  Rime `coda` model, speaker `astra`, use_websocket=True
  │         (word-level timestamps enable precise mid-utterance cut)
  └─ Turn Fencing Layer (custom, see below)
```

## Turn fencing layer (the core hard-voice mechanism)

State: a single monotonically-increasing `turn_id` int, owned by the
`AgentSession`.

1. On each confirmed user turn (end-of-utterance), increment `turn_id`.
2. When dispatching a tool call, capture `dispatch_turn_id = turn_id` in a
   closure/dataclass alongside the `asyncio.Task`.
3. Concurrently with tool dispatch, call `session.say(filler_text,
   add_to_chat_ctx=False)` without awaiting it — this is what makes the
   filler phrase and the tool call run in parallel instead of sequentially.
4. When the tool task resolves:
   - Compare `dispatch_turn_id` to the session's *current* `turn_id`.
   - Match → cancel any still-playing filler, speak the real result as part
     of the same assistant turn.
   - Mismatch (a newer user turn has started) → drop the result, do not
     speak it, do not add it to the chat context, log it to evidence output
     for the demo/README ("stale result discarded").
5. On detected user interruption (`speech_handle.interrupted` becomes true):
   - Let LiveKit's default behavior stop queued Rime audio (do not
     reimplement this).
   - Explicitly cancel the tool `asyncio.Task` tied to the now-superseded
     `turn_id` using a `cancel_and_wait`-style helper, so the 3-second sleep
     doesn't keep running uselessly in the background.
   - Immediately route the new transcript into turn `turn_id + 1`.

## Tricky integration points

- **Race window:** a tool can resolve in the exact instant a new user turn
  starts. The fencing check must happen right before *speaking*, not only at
  dispatch — checking only at dispatch time is a common but insufficient
  implementation.
- **One turn, not two:** filler + final answer must collapse into a single
  assistant chat-history entry. Use `add_to_chat_ctx=False` on the filler
  `say()` call, then let only the final combined response be recorded.
- **False positives:** rack ambience/coughs can trip VAD. Tune
  `interruption.resume_false_interruption` rather than writing custom
  debounce logic — this is a framework-provided setting for exactly this
  failure mode.
- **Voice availability drift:** Rime's live catalog can change between build
  time and submission time. A startup preflight check (hit the live voices
  endpoint, assert `astra` is present under `coda`) should run before the
  agent boots, and its result should be logged so it's visible in the demo.
- **Credential handling:** all keys (LiveKit, Rime, STT, LLM) live in
  server-side env vars only, loaded by the agent worker process — never
  passed to or logged by the browser client.

## Reproducibility hook

`RIME_EVIDENCE.md`'s repeatable script should drive the acceptance test
programmatically: inject the tool call, wait a controlled interval shorter
than the 3s delay, then simulate the interrupting transcript via LiveKit's
text-injection/test harness rather than requiring a human to time a real
voice interruption on every re-run.
