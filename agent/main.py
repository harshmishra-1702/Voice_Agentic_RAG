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

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, ".env"))
load_dotenv()  # Fallback to cwd if present

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
    from .providers import get_stt_adapter, get_llm_adapter, get_tts_adapter
    
    stt_plugin = get_stt_adapter().get_plugin()
    llm_plugin = get_llm_adapter().get_plugin()
    tts_plugin = get_tts_adapter().get_plugin()
    
    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin
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

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket) -> None:
        if data_packet.topic == "browser_context":
            try:
                payload = json.loads(data_packet.data.decode("utf-8"))
                agent.update_browser_context(payload)
            except Exception as e:
                logger.warning(f"Failed to parse browser context: {e}")

    # ── Start the session ───────────────────────────────────────────
    await session.start(room=ctx.room, agent=agent)

    # ── Initial greeting ────────────────────────────────────────────
    await session.say(
        "VoiceOps online. What do you need?",
        allow_interruptions=True,
    )
    logger.info("Session started — VoiceOps agent is live")


if __name__ == "__main__":
    agents.cli.run_app(server)
