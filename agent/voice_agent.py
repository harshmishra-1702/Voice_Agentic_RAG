"""
VoiceOps Agent — Agent subclass with two @function_tool methods
and integrated turn-fencing + filler-phrase logic.

Tools:
  - query_runbook_rag(query) — semantic search with simulated 3s delay
  - check_server_status(host) — mocked async ping with 0.5-1.5s delay

The filler phrase fires concurrently with the tool call (not awaited first),
and the turn-fencing check happens right before speaking the result.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any

from livekit.agents import Agent, RunContext, function_tool

from .rag import search_runbooks
from .turn_fence import TurnFenceManager

logger = logging.getLogger("voiceops.agent")

# Filler phrases — rotated to avoid sounding canned on camera
RAG_FILLERS = [
    "Scanning the outage runbooks now\u2026",
    "Searching through the incident procedures\u2026",
    "Pulling up the relevant documentation\u2026",
]

STATUS_FILLERS = [
    "Checking that server now\u2026",
    "Pinging the host\u2026",
    "Running a quick status check\u2026",
]

# Mocked server status responses
MOCK_STATUSES = [
    {"status": "healthy", "cpu_percent": 23.4, "memory_percent": 61.2, "uptime": "14d 6h 32m"},
    {"status": "degraded", "cpu_percent": 87.1, "memory_percent": 92.3, "uptime": "2d 11h 05m"},
    {"status": "healthy", "cpu_percent": 45.0, "memory_percent": 55.8, "uptime": "31d 0h 14m"},
]


class VoiceOpsAgent(Agent):
    """SRE runbook copilot with turn-fenced tool calls."""

    def __init__(self, turn_fence: TurnFenceManager) -> None:
        super().__init__(
            instructions=(
                "You are VoiceOps, a concise SRE runbook copilot. "
                "The user is a Site Reliability Engineer with both hands busy "
                "inside a server rack — they can only interact by voice. "
                "Keep spoken answers to 1-2 sentences. Summarize key steps "
                "from runbooks rather than reading them verbatim. "
                "When checking server status, report the essentials: host, "
                "status, and any concerning metrics. "
                "If a tool fails, say so explicitly — never go silent."
            ),
        )
        self.turn_fence = turn_fence
        self._filler_index: int = 0
        self._data_channel_send: Any = None  # Set by main.py for UI updates

    def _next_filler(self, pool: list[str]) -> str:
        """Rotate through filler phrases so they don't repeat consecutively."""
        phrase = pool[self._filler_index % len(pool)]
        self._filler_index += 1
        return phrase

    async def _send_ui_event(self, event: dict[str, Any]) -> None:
        """Send a status event to the frontend via data channel."""
        if self._data_channel_send is not None:
            try:
                await self._data_channel_send(json.dumps(event))
            except Exception:
                logger.debug("Failed to send UI event", exc_info=True)

    @function_tool(description="Search the SRE runbooks for procedures, recovery steps, or troubleshooting guides.")
    async def query_runbook_rag(self, query: str) -> str:
        session = self.session
        dispatch_turn = self.turn_fence.current_turn_id

        # Fire filler phrase concurrently — do NOT await before starting the search
        filler = self._next_filler(RAG_FILLERS)
        session.say(filler, add_to_chat_ctx=False, allow_interruptions=True)

        # Notify UI
        await self._send_ui_event({
            "event": "tool_start",
            "tool": "query_runbook_rag",
            "query": query,
            "turn_id": dispatch_turn,
        })

        try:
            # Simulate slow/dense-corpus search (3-second delay per spec)
            await asyncio.sleep(3)

            # Check staleness BEFORE doing the actual search work
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                await self._send_ui_event({
                    "event": "stale_discard",
                    "tool": "query_runbook_rag",
                    "from_turn": dispatch_turn,
                    "to_turn": self.turn_fence.current_turn_id,
                })
                return ""  # Empty return — LLM won't speak this

            # Actual RAG search
            results = await search_runbooks(query, top_k=3)

            # Check staleness AGAIN right before returning (race condition guard)
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                await self._send_ui_event({
                    "event": "stale_discard",
                    "tool": "query_runbook_rag",
                    "from_turn": dispatch_turn,
                    "to_turn": self.turn_fence.current_turn_id,
                })
                return ""

            # Notify UI of completion
            await self._send_ui_event({
                "event": "tool_complete",
                "tool": "query_runbook_rag",
                "turn_id": dispatch_turn,
                "result_count": len(results),
            })

            self.turn_fence.mark_complete(dispatch_turn)

            if not results:
                return "No matching runbook entries found for that query."

            # Format results for the LLM to summarize
            formatted = "\n\n".join(
                f"[Source: {r.source}] (relevance: {r.score:.2f})\n{r.text}"
                for r in results
            )
            return (
                f"Found {len(results)} relevant runbook sections:\n\n{formatted}\n\n"
                "Summarize the key recovery steps in 1-2 sentences for the user."
            )

        except asyncio.CancelledError:
            logger.info("RAG search cancelled (turn %d superseded)", dispatch_turn)
            return ""
        except Exception as e:
            logger.exception("RAG search failed")
            await self._send_ui_event({
                "event": "tool_error",
                "tool": "query_runbook_rag",
                "error": str(e),
            })
            return f"I'm sorry, the runbook search failed: {e}. Please try again."

    @function_tool()
    async def check_server_status(self, ctx: RunContext, host: str) -> str:
        """Check the current status of a server or rack by hostname.

        Args:
            host: The hostname or rack identifier to check (e.g. rack-14, web-server-01).
        """
        session = ctx.session
        dispatch_turn = self.turn_fence.current_turn_id

        # Fire filler concurrently
        filler = self._next_filler(STATUS_FILLERS)
        session.say(filler, add_to_chat_ctx=False, allow_interruptions=True)

        # Notify UI
        await self._send_ui_event({
            "event": "tool_start",
            "tool": "check_server_status",
            "host": host,
            "turn_id": dispatch_turn,
        })

        try:
            # Simulated async ping with randomized delay (0.5–1.5s)
            delay = random.uniform(0.5, 1.5)
            await asyncio.sleep(delay)

            # Staleness check before speaking
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                await self._send_ui_event({
                    "event": "stale_discard",
                    "tool": "check_server_status",
                    "from_turn": dispatch_turn,
                    "to_turn": self.turn_fence.current_turn_id,
                })
                return ""

            # Mocked response
            mock = random.choice(MOCK_STATUSES)
            response = {
                "host": host,
                "status": mock["status"],
                "cpu_percent": mock["cpu_percent"],
                "memory_percent": mock["memory_percent"],
                "uptime": mock["uptime"],
                "latency_ms": round(delay * 1000),
                "checked_at": time.strftime("%H:%M:%S UTC", time.gmtime()),
            }

            # Notify UI
            await self._send_ui_event({
                "event": "tool_complete",
                "tool": "check_server_status",
                "turn_id": dispatch_turn,
                "result": response,
            })

            self.turn_fence.mark_complete(dispatch_turn)

            return (
                f"Server status for {host}: {response['status']}. "
                f"CPU at {response['cpu_percent']}%, "
                f"memory at {response['memory_percent']}%, "
                f"uptime {response['uptime']}, "
                f"latency {response['latency_ms']}ms."
            )

        except asyncio.CancelledError:
            logger.info("Status check cancelled (turn %d superseded)", dispatch_turn)
            return ""
        except Exception as e:
            logger.exception("Status check failed")
            await self._send_ui_event({
                "event": "tool_error",
                "tool": "check_server_status",
                "error": str(e),
            })
            return f"I'm sorry, the status check for {host} failed: {e}."
