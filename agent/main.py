"""
VoiceOps Agent Worker — LiveKit AgentServer entrypoint.

Wires together: Deepgram STT, GPT-4o-mini LLM, Rime TTS (coda/astra),
Silero VAD, turn-fencing, and session event handlers for interruption
recovery.
"""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()  # Load .env before anything else touches env vars

from livekit import agents, rtc
from livekit.plugins import deepgram, openai, rime
from livekit.agents import AgentServer, AgentSession, JobContext

from .preflight import validate_rime_voice
from .turn_fence import TurnFenceManager
from .voice_agent import VoiceOpsAgent

logger = logging.getLogger("voiceops.main")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

server = AgentServer()


@server.rtc_session(agent_name="voiceops")
async def entrypoint(ctx: JobContext) -> None:
    """Session entrypoint — called for each new LiveKit room connection."""

    # ── Rime preflight ──────────────────────────────────────────────
    voice_ok = await validate_rime_voice(model="coda", speaker="astra")
    if voice_ok:
        logger.info("Rime preflight passed — coda/astra confirmed available")
    else:
        logger.warning("Rime preflight could not confirm voice — proceeding anyway")

    # ── Initialize turn fencing ─────────────────────────────────────
    turn_fence = TurnFenceManager()

    # ── Create the Agent ────────────────────────────────────────────
    agent = VoiceOpsAgent(turn_fence=turn_fence)

    # ── Configure session ───────────────────────────────────────────
    # Groq LLM via OpenAI-compatible plugin (free tier)
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    session = AgentSession(
        stt=deepgram.STT(
            model="nova-3",
            language="en",
            punctuate=True,
            smart_format=True,
        ),
        llm=openai.LLM(
            model="llama-3.3-70b-versatile",
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_api_key,
            temperature=0.6,
        ),
        tts=rime.TTS(
            model="coda",
            speaker="astra",
            use_websocket=True,  # MANDATORY — streaming + word-level timestamps
        )
    )

    # ── Wire interruption events to the turn fence ──────────────────

    @session.on("user_started_speaking")
    def on_user_speech_start() -> None:
        """Fires when VAD detects user speech onset.

        Advance the turn counter and cancel any stale in-flight tool tasks.
        LiveKit's default behavior already stops queued Rime audio — we
        don't fight that, we just clean up the async task side.
        """
        new_turn = turn_fence.advance_turn()
        logger.info("User started speaking — advanced to turn %d", new_turn)

        # Schedule stale task cancellation (can't await in sync handler)
        import asyncio
        asyncio.ensure_future(turn_fence.cancel_all_stale())

    @session.on("agent_speech_interrupted")
    def on_agent_interrupted() -> None:
        """Fires when the agent's speech is interrupted by the user.

        Log it for evidence — the actual audio stop is handled by LiveKit,
        and task cancellation was triggered in on_user_speech_start.
        """
        logger.info(
            "Agent speech interrupted at turn %d",
            turn_fence.current_turn_id,
        )

    # ── Wire discard events to data channel for UI ──────────────────
    async def send_data_message(payload: str) -> None:
        """Send a JSON message to the frontend via LiveKit data channel."""
        try:
            data = payload.encode("utf-8")
            await ctx.room.local_participant.publish_data(
                data, reliable=True, topic="voiceops_status"
            )
        except Exception:
            logger.debug("Data channel send failed", exc_info=True)

    # Give the agent access to the data channel sender
    agent._data_channel_send = send_data_message

    # Register discard listener for UI notifications
    def on_discard(event: object) -> None:
        import asyncio
        asyncio.ensure_future(
            send_data_message(json.dumps(event.to_dict()))  # type: ignore[union-attr]
        )

    turn_fence.on_discard(on_discard)

    # ── Start the session ───────────────────────────────────────────
    await session.start(room=ctx.room, agent=agent)

    # ── Initial greeting ────────────────────────────────────────────
    await session.say(
        "VoiceOps online. I can search the runbooks or check server status. "
        "What do you need?",
        allow_interruptions=True,
    )
    logger.info("Session started — VoiceOps agent is live")


if __name__ == "__main__":
    agents.cli.run_app(server)
