"""
Turn Fencing State Machine — the core hard-voice mechanism for VoiceOps.

Guarantees that stale tool results (from a superseded user turn) are never
spoken or added to the LLM context, even when they resolve after the user
has already redirected the conversation.

The staleness check happens at TWO points:
  1. At dispatch time (early exit if the turn already advanced)
  2. Right before speaking the result (the critical check — a tool can
     resolve in the exact instant a new turn starts)

This module is intentionally self-contained. All fencing state lives here,
not scattered across handlers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger("voiceops.turn_fence")


@dataclass
class DispatchedTask:
    """A tool invocation tagged with the turn_id that spawned it."""

    task: asyncio.Task[Any]
    dispatch_turn_id: int
    tool_name: str
    created_at: float = field(default_factory=time.time)


@dataclass
class DiscardEvent:
    """Record of a stale result that was dropped — surfaced in the UI and
    written to RIME_EVIDENCE.md's output log."""

    tool_name: str
    dispatch_turn_id: int
    current_turn_id: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "stale_discard",
            "tool": self.tool_name,
            "from_turn": self.dispatch_turn_id,
            "to_turn": self.current_turn_id,
            "timestamp": self.timestamp,
        }


class TurnFenceManager:
    """Monotonic turn-id tracker with task dispatch, staleness checking,
    and cancellation.

    Usage:
        fence = TurnFenceManager()

        # When a new user turn is detected (VAD end-of-utterance):
        new_id = fence.advance_turn()

        # When dispatching a tool call:
        dispatched = fence.dispatch(some_coro(), "query_runbook_rag")

        # Before speaking the result:
        if fence.is_stale(dispatched.dispatch_turn_id):
            await fence.cancel_stale(dispatched.dispatch_turn_id)
        else:
            # speak the result
            ...
    """

    def __init__(self) -> None:
        self._current_turn_id: int = 0
        self._active_tasks: dict[int, DispatchedTask] = {}
        self._discard_log: list[DiscardEvent] = []
        self._listeners: list[Callable[[DiscardEvent], None]] = []

    @property
    def current_turn_id(self) -> int:
        return self._current_turn_id

    @property
    def discard_log(self) -> list[DiscardEvent]:
        return list(self._discard_log)

    def on_discard(self, callback: Callable[[DiscardEvent], None]) -> None:
        """Register a listener that fires whenever a stale result is discarded.
        Used by the UI bridge to show the on-screen indicator."""
        self._listeners.append(callback)

    def advance_turn(self) -> int:
        """Increment the turn counter. Called on each confirmed user turn."""
        self._current_turn_id += 1
        logger.info("Turn advanced to %d", self._current_turn_id)
        return self._current_turn_id

    def is_stale(self, dispatch_turn_id: int) -> bool:
        """Check whether a dispatched task's turn is still current.

        This MUST be called right before speaking — not only at dispatch time.
        A tool can resolve in the exact instant a new user turn starts.
        """
        stale = dispatch_turn_id < self._current_turn_id
        if stale:
            logger.info(
                "Turn %d is stale (current: %d)",
                dispatch_turn_id,
                self._current_turn_id,
            )
        return stale

    def dispatch(
        self,
        coro: Coroutine[Any, Any, Any],
        tool_name: str,
    ) -> DispatchedTask:
        """Wrap a coroutine in an asyncio.Task, tag it with the current turn_id.

        Returns the DispatchedTask immediately (non-blocking).
        """
        turn_id = self._current_turn_id
        task = asyncio.create_task(coro, name=f"{tool_name}@turn-{turn_id}")
        dispatched = DispatchedTask(
            task=task,
            dispatch_turn_id=turn_id,
            tool_name=tool_name,
        )
        self._active_tasks[turn_id] = dispatched
        logger.info(
            "Dispatched tool '%s' at turn %d", tool_name, turn_id
        )
        return dispatched

    async def cancel_stale(self, turn_id: int) -> None:
        """Cancel a task tied to a stale turn and log the discard event.

        Uses cancel-and-wait pattern to ensure the task is fully stopped
        before we move on — prevents the 3-second sleep from running
        uselessly in the background.
        """
        dispatched = self._active_tasks.pop(turn_id, None)
        if dispatched is None:
            return

        # Cancel the asyncio task
        if not dispatched.task.done():
            dispatched.task.cancel()
            try:
                await dispatched.task
            except asyncio.CancelledError:
                pass

        # Log the discard
        event = DiscardEvent(
            tool_name=dispatched.tool_name,
            dispatch_turn_id=turn_id,
            current_turn_id=self._current_turn_id,
        )
        self._discard_log.append(event)
        logger.warning(
            "Stale result discarded: tool='%s' dispatched_turn=%d current_turn=%d",
            event.tool_name,
            event.dispatch_turn_id,
            event.current_turn_id,
        )

        # Notify listeners (for UI)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Discard listener error")

    async def cancel_all_stale(self) -> None:
        """Cancel every active task whose turn_id is older than current.
        Called when a new user turn is detected mid-tool-call."""
        stale_ids = [
            tid
            for tid in list(self._active_tasks.keys())
            if tid < self._current_turn_id
        ]
        for tid in stale_ids:
            await self.cancel_stale(tid)

    def mark_complete(self, turn_id: int) -> None:
        """Remove a task from tracking after it has been successfully
        spoken (not stale). Prevents double-cancel."""
        self._active_tasks.pop(turn_id, None)

    def get_active_tool(self) -> DispatchedTask | None:
        """Return the most recent active task, if any."""
        if not self._active_tasks:
            return None
        latest_id = max(self._active_tasks.keys())
        return self._active_tasks[latest_id]
