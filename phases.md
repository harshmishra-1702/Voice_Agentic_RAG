# Build Phases — VoiceOps

Assumes solo dev, Python-comfortable, no prior LiveKit experience. All API
keys (LiveKit, Rime, STT, LLM) should be acquired and smoke-tested *before*
Phase 0 starts — don't let key provisioning eat into build time.

| Phase | Work | Est. hours |
|---|---|---|
| 0 | Project scaffolding, LiveKit room setup, one-off Rime API call test, live-catalog preflight script | 2–3 |
| 1 | Minimal voice loop: VAD → STT → LLM (no tools) → Rime TTS, one working round-trip | 2–3 |
| 2 | Add both function tools with mocked delays; confirm LLM routes correctly between them | 3–4 |
| 3 | Filler-phrase pattern: concurrent `say(add_to_chat_ctx=False)` + tool task | 2–3 |
| 4 | Turn-fencing + interruption cancellation (the hard part — budget generously) | 4–6 |
| 5 | Build small runbook corpus (5–10 docs) + Chroma ingestion | 2 |
| 6 | `RIME_EVIDENCE.md` + a runnable script that reproduces the stress test without manual timing | 2–3 |
| 7 | README, `.env.example`, credential hygiene pass, final preflight check | 1–2 |
| 8 | Record demo (expect retakes) | 2–3 |
| — | Buffer for the inevitable | 3–4 |

**Total: ~24–30 hours.** Realistically a full hackathon weekend at a
sustainable pace, not a single overnight push — Phase 4 in particular tends
to blow past estimates because the race-condition bugs it produces are timing
-dependent and annoying to reproduce.

## Cut list if time runs short (in order of what to drop first)
1. Second tool's realism (keep `check_server_status` maximally trivial).
2. UI polish beyond the transcript + provider badge + stale-result toast.
3. Corpus size — 3 well-chosen runbook chunks are enough to prove the point.

## Never cut, even under time pressure
- The turn-fencing mechanism itself — it's 25% + 20% of the score.
- The repeatable evidence script — "unverified performance numbers receive
  no credit" per the brief.
- Credential hygiene — this is an instant-disqualification clause.
