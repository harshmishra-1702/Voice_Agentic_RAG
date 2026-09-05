# Design — VoiceOps

## Interaction model
Continuous listening with VAD-based barge-in — **no push-to-talk button.**
A PTT button would require a free hand, which directly contradicts the
hands-busy SRE premise and would visibly undercut the "necessity of voice"
judging criterion.

## Voice & persona
- Model: `coda`, speaker: `astra` (Rime-documented starter voice, confirmed
  present on Coda). Neutral, clear, technical tone — no need for an
  expressive/character voice for this use case.
- Spoken turns kept short (1–2 sentences), per Rime's own "design for real
  use" guidance — dense technical answers should be summarized aloud, with
  full detail available in an on-screen transcript, not spoken verbatim.
- Filler phrases are short and non-repetitive across a session (rotate 2–3
  variants) so they don't read as a canned stall tactic on the demo video.

## Visual design system

The UI is secondary to the voice channel functionally, but it's what judges
watch on camera for 4-5 minutes — it needs to look like a deliberate product,
not a default AI-scaffolded page. "Big, glanceable components" isn't just an
aesthetic preference here — it's the right call for the subject matter: an
SRE isn't reading fine print while their hands are in a rack, so the screen
(what little they glance at) should read at a distance, not up close.

**Color** — dark base, single disciplined orange accent (not the muted
terracotta that most AI-generated dark UIs default to):
- `--bg`: `#14110D` — warm near-black (deliberately not `#0B0B0B`/`#111`,
  which read as generic-AI tinted-black)
- `--surface`: `#1F1A14` — panel background
- `--surface-raised`: `#2A2118` — the active-tool status chip only
- `--accent`: `#FF6A00` — true saturated orange, used in exactly one place
  at a time (mic-live pulse, or the primary action), never smeared across
  every border/button
- `--accent-muted`: `#C97A2E` — secondary/inactive states
- `--text`: `#F5EFE6`
- `--text-muted`: `#9A8F80`

**Type** — two clearly distinct families, not a display/body split from the
same font:
- Headings & the provider badge: **Space Grotesk** — has an industrial,
  technical character that fits the server-rack subject matter.
- Transcript & body text: **IBM Plex Sans** — highly legible at a glance.
- **IBM Plex Mono**, used sparingly and only for real technical values
  (turn IDs, timestamps, hostnames) — not as generic label styling.

**Layout** — single-column "console," left-aligned, not a marketing page:
```
+--------------------------------------------------+
| VoiceOps                 [● Rime — coda / astra]  |
+--------------------------------------------------+
|                                                    |
|         (( live waveform reacts to audio ))       |  <- the hero:
|                                                    |     the act of
+--------------------------------------------------+     speaking,
| [ Searching runbooks... ]  <- big pill, one job    |     not copy
+--------------------------------------------------+
| Live transcript                                   |
|  You:    ...                                      |
|  Agent:  ...                                      |
|  ⚠ stale result discarded (turn 3 → turn 4)        |
+--------------------------------------------------+
```
The hero element is the live waveform/orb, not a headline — for a voice
product, the moment of speaking *is* the most characteristic thing in its
world.

**Principles / anti-vibecoded checklist** — explicitly avoid:
- Identical rounded cards with the same soft grey shadow on every panel
  (the status chip, transcript panel, and provider badge should each have a
  distinct shape suited to its job — pill, borderless-with-rule, small
  swatch — not the same card three times).
- ALL-CAPS tracked-out labels, middle-dot meta strings, arrow-suffixed
  buttons ("Connect →").
- Scattered fade-in-on-scroll animation on every element. One deliberate
  motion only: the waveform reacting live to audio amplitude.
- Gradient washes as decoration.

## Functional UI elements
- Live transcript of both sides of the conversation, in IBM Plex Sans.
- Active speech provider badge ("Rime — coda / astra"), satisfying the
  "make the active speech provider observable" build rule.
- A big status pill for the in-flight tool ("Searching runbooks…" /
  "Checking rack-14…") so judges can visually correlate what's happening
  with what they hear — this doubles as your own debugging aid for timing
  the stress test.
- A visible, on-brand indicator when a stale tool result is discarded (in
  monospace, showing the turn IDs involved), so the fencing behavior —
  otherwise invisible/silent by design — is demonstrable on camera.

## Demo script (for the 4-5 min recording)
1. 20s: introduce the user, problem, and why voice is structurally necessary.
2. 60s: normal end-to-end flow — ask a runbook question, get an answer.
3. 90s: the stress case — trigger the slow RAG tool, interrupt mid-filler,
   redirect to the status tool, show the stale result being discarded.
4. 30s: show the RIME_EVIDENCE.md script re-running the same test
   programmatically, proving it's not a one-off.
5. 20s: close on the active-provider badge and known limitations.
