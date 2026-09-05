# PRD — VoiceOps: Voice-Native SRE Runbook Copilot

## 1. Problem
An SRE with both hands inside a live server rack cannot type, tap, or read a
screen, but still needs to consult dense internal runbooks and check system
status. A screen-based chatbot is unusable here; voice is not a convenience,
it's the only viable interface. This maps directly to the hackathon's
"Problem and necessity of voice" criterion (25%): removing speech would make
the product unusable, not just less convenient.

## 2. Target user
Site Reliability Engineer, mid-incident, hands occupied with hardware.

## 3. Chosen hard-voice problem (per hackathon brief)
Combined: **Interruption and recovery** + **Conversation continuity during
tool work**. Both are listed as directions rather than separate scoring
tracks, and the two failure modes overlap naturally in this scenario: a slow
tool call (runbook search) plus a mid-task verbal correction from the user.

## 4. Goals
- Prove that queued Rime audio halts immediately on user interruption.
- Prove that a stale, slow-resolving tool result can never re-enter the
  conversation after the user has moved on.
- Prove this with a scripted, repeatable test — not a one-time recorded
  fluke.

## 5. Non-goals (explicitly out of scope for this build)
- Real runbook ingestion pipeline / real monitoring integrations.
- Telephony transport (browser/WebRTC via LiveKit is sufficient and matches
  the brief's "hands-busy tasks" fit).
- Multi-user sessions, auth, persistence across sessions.
- Multilingual support.
- A polished/production RAG system — a small curated Chroma corpus is enough
  to demonstrate the tool-call fencing behavior.

## 6. Success metrics (map directly to judging weights)
| Criterion | Weight | How this PRD satisfies it |
|---|---|---|
| Problem & necessity of voice | 25% | Hands-busy SRE scenario; voice is structurally required |
| Hard voice engineering | 25% | Turn-fencing + interruption recovery under a real async race condition |
| Rime integration & experience | 20% | `coda` + `astra`, websocket streaming, word-level timestamps used for fencing |
| Evidence & reproducibility | 20% | Scripted stress-test fixture in `RIME_EVIDENCE.md`, not manual demo-only proof |
| Demo clarity | 10% | Single clear before/interrupt/after sequence, ~4-5 min |

## 7. Risks / open questions
- Voice availability on `coda` can change before submission — the live
  catalog must be checked programmatically at build time and again right
  before recording the demo.
- False-interruption noise (ambient rack sound) could make the demo look
  unstable if not tuned — budget time to tune VAD/turn-detection settings,
  not just the fencing logic.
- If the LLM's function-calling plugin doesn't reliably route between two
  tools, the whole acceptance test collapses — smoke-test tool routing before
  investing in the fencing logic.
