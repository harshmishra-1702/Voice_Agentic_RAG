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

from .rag import search_knowledge
from .turn_fence import TurnFenceManager

logger = logging.getLogger("voiceops.agent")

# Filler phrases — rotated to avoid sounding canned on camera
RAG_FILLERS = [
    "Searching the uploaded documents now\u2026",
    "Looking through the indexed files\u2026",
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
        import datetime
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        super().__init__(
            instructions=(
                f"You are an AI Voice Copilot & Research Assistant with direct vector search access to user-uploaded documents and live web search capabilities.\n"
                f"The current date and time is: {current_date}.\n\n"
                "PRIMARY DIRECTIVE:\n"
                "1. ALWAYS SEARCH THE KNOWLEDGE BASE: Whenever the user asks a question about their uploaded file, project review, presentation, or document, you MUST IMMEDIATELY call the `query_knowledge_base` tool.\n"
                "2. USE WEB SEARCH FOR RECENT OR GENERAL INFO: If the user asks a question that requires internet access or looking up real-world recent information, use the `search_the_web` tool via Tavily.\n"
                "3. NEVER CLAIM YOU CAN'T SEE FILES: NEVER say 'I don't see a file attached' or 'Please upload the file'. Always call `query_knowledge_base` to retrieve the relevant information!\n"
                "4. SPOKEN PROSE FORMATTING: You are speaking directly via Text-To-Speech. NEVER use markdown formatting like asterisks (**), hashes (##), backticks (```), or bullet points. Speak in clear, natural, conversational sentences (1-3 sentences per turn).\n"
                "5. ACCURACY: Base your answers directly on the retrieved source excerpts or web results."
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

    def update_browser_context(self, context: dict[str, Any]) -> None:
        """Update the agent's system prompt or internal state with the latest browser context."""
        url = context.get("url", "")
        title = context.get("title", "")
        selection = context.get("selection", "")
        
        # We can store this in the agent and optionally inject it into the LLM context if asked
        self._latest_browser_context = context
        
        context_str = f"Current User Browser Context: URL={url}, Title={title}"
        if selection:
            context_str += f", Selection='{selection}'"
            
        # Update system instructions dynamically by appending the context
        # In a real app we'd update the prompt dynamically per turn,
        # but here we'll just keep it as a property the tools can read if needed,
        # or we could push a system message.
        self._system_prompt_context = context_str

    async def _send_ui_event(self, event: dict[str, Any]) -> None:
        """Send a status event to the frontend via data channel."""
        if self._data_channel_send is not None:
            try:
                await self._data_channel_send(json.dumps(event))
            except Exception:
                logger.debug("Failed to send UI event", exc_info=True)

    @function_tool(description="Search and retrieve information from all user-uploaded files (PDFs, PPTs, Cloud project reviews, documents) and the knowledge base.")
    async def query_knowledge_base(self, query: str) -> str:
        session = self.session
        dispatch_turn = self.turn_fence.current_turn_id

        # Fire filler phrase concurrently — do NOT await before starting the search
        filler = self._next_filler(["Searching the educational corpus...", "Looking that up in the knowledge base...", "Checking the primary sources..."])
        session.say(filler, add_to_chat_ctx=False, allow_interruptions=True)

        # Notify UI
        await self._send_ui_event({
            "event": "tool_start",
            "tool": "query_knowledge_base",
            "query": query,
            "turn_id": dispatch_turn,
        })

        try:
            # We don't simulate a 3-second delay here anymore, just a brief one so turn fencing can still happen if interrupted quickly
            await asyncio.sleep(0.5)

            # Check staleness BEFORE doing the actual search work
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                await self._send_ui_event({
                    "event": "stale_discard",
                    "tool": "query_knowledge_base",
                    "from_turn": dispatch_turn,
                    "to_turn": self.turn_fence.current_turn_id,
                })
                return ""  # Empty return — LLM won't speak this

            from .rag import search_knowledge
            results = await search_knowledge(query, top_k=3)

            # Check staleness AGAIN right before returning (race condition guard)
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                await self._send_ui_event({
                    "event": "stale_discard",
                    "tool": "query_knowledge_base",
                    "from_turn": dispatch_turn,
                    "to_turn": self.turn_fence.current_turn_id,
                })
                return ""

            # Notify UI of completion
            await self._send_ui_event({
                "event": "tool_complete",
                "tool": "query_knowledge_base",
                "turn_id": dispatch_turn,
                "result_count": len(results),
            })

            self.turn_fence.mark_complete(dispatch_turn)

            if not results:
                return "No matching educational entries found for that query."

            # Format results for the LLM to summarize, stripping null bytes and weird unicode
            formatted = "\n\n".join(
                f"[Source: {r.source_title}, Evidence Level: {r.evidence_level}] (relevance: {r.score:.2f})\n{r.text.replace(chr(0), '')}"
                for r in results
            )
            prompt_str = (
                f"Found {len(results)} relevant source sections:\n\n{formatted}\n\n"
                "Carefully answer the user's question using the information above. "
                "Make sure to explicitly cite the source and distinguish between toy-model behavior and published evidence. "
                "CRITICAL: Keep your response extremely concise, direct, and conversational (1-3 sentences maximum) to minimize audio generation delay. "
                "DO NOT use markdown formatting, bullet points, or special characters like asterisks or hashes in your spoken response."
            )
            print(f"RAG search successful. Returned {len(results)} chunks to LLM.", flush=True)
            return prompt_str

        except asyncio.CancelledError:
            logger.info("RAG search cancelled (turn %d superseded)", dispatch_turn)
            return ""
        except Exception as e:
            logger.exception("RAG search failed")
            await self._send_ui_event({
                "event": "tool_error",
                "tool": "query_knowledge_base",
                "error": str(e),
            })
            return f"I'm sorry, the knowledge search failed: {e}. Please try again."

    @function_tool(description="Run the MemoryLab recurrent memory experiment with specified parameters.")
    async def run_memory_experiment(self, sequence_str: str, memory_size: int = 8, update_strength: float = 0.6, interference: float = 0.1) -> str:
        dispatch_turn = self.turn_fence.current_turn_id
        session = self.session
        filler = self._next_filler(["Running the memory experiment...", "Computing memory state...", "Simulating the recurrent memory..."])
        session.say(filler, add_to_chat_ctx=False, allow_interruptions=True)
        
        await self._send_ui_event({
            "event": "tool_start",
            "tool": "run_memory_experiment",
            "turn_id": dispatch_turn,
        })
        
        try:
            from .education.experiment_engine import run_experiment
            sequence = [x.strip() for x in sequence_str.replace(',', ' ').split() if x.strip()]
            
            # Simulated short computation time
            await asyncio.sleep(0.2)
            
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                return ""
            
            res = run_experiment(sequence, memory_size, update_strength, interference, 42)
            
            await self._send_ui_event({
                "event": "tool_complete",
                "tool": "run_memory_experiment",
                "turn_id": dispatch_turn,
                "metrics": res["metrics"]
            })
            self.turn_fence.mark_complete(dispatch_turn)
            
            return f"Experiment completed. Metrics: {res['metrics']}. The UI has been updated."
        except asyncio.CancelledError:
            return ""
        except Exception as e:
            logger.exception("Experiment failed")
            return f"Experiment failed: {e}"

    @function_tool(description="Explain why the memory state or retrieval score resulted in a certain way.")
    async def explain_memory_state(self, question: str) -> str:
        dispatch_turn = self.turn_fence.current_turn_id
        session = self.session
        session.say("Let's look at the memory state...", add_to_chat_ctx=False, allow_interruptions=True)
        
        try:
            await asyncio.sleep(0.1)
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                return ""
            self.turn_fence.mark_complete(dispatch_turn)
            return "Based on the toy model's recurrent update, earlier items suffer from interference and capacity limits. Explain this clearly in your response."
        except asyncio.CancelledError:
            return ""

    @function_tool(description="Get BDH evidence and comparison for a specific concept, e.g., 'recurrent_memory'")
    async def get_bdh_evidence(self, concept: str) -> str:
        dispatch_turn = self.turn_fence.current_turn_id
        session = self.session
        session.say("Checking the BDH evidence module...", add_to_chat_ctx=False, allow_interruptions=True)
        
        try:
            await asyncio.sleep(0.1)
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                return ""
            
            from .education.bdh import get_bdh_evidence as bdh_ev
            evidence = bdh_ev(concept)
            
            self.turn_fence.mark_complete(dispatch_turn)
            if evidence:
                return f"BDH Evidence for '{concept}': {evidence}. Please explain this to the user."
            else:
                return "I don't have enough source evidence to make that claim."
        except asyncio.CancelledError:
            return ""

    @function_tool(description="Check the user's current browser context (URL, Title, Selection)")
    async def check_browser_context(self) -> str:
        dispatch_turn = self.turn_fence.current_turn_id
        session = self.session
        session.say("Checking your browser screen...", add_to_chat_ctx=False, allow_interruptions=True)
        
        try:
            await asyncio.sleep(0.1)
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                return ""
            
            self.turn_fence.mark_complete(dispatch_turn)
            ctx_str = getattr(self, "_system_prompt_context", None)
            
            # Also try to read from the extension's written file if it exists
            import os
            import json
            context_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".browser_context.json")
            if os.path.exists(context_file):
                try:
                    with open(context_file, "r") as f:
                        ext_ctx = json.load(f)
                    url = ext_ctx.get("url", "")
                    title = ext_ctx.get("title", "")
                    selection = ext_ctx.get("selection", "")
                    ctx_str = f"Extension Context: URL={url}, Title={title}"
                    if selection:
                        ctx_str += f", Selection='{selection}'"
                except Exception:
                    pass
                    
            if not ctx_str:
                ctx_str = "No browser context available."
                
            return f"Browser Context: {ctx_str}. If you need the full text of the page to answer the user's question, use the read_website_content tool with the URL."
        except asyncio.CancelledError:
            return ""

    @function_tool(description="Extract and read the full markdown content of any website URL using the Jina AI Reader API. Use this when the user asks a question about a specific webpage URL.")
    async def read_website_content(self, url: str) -> str:
        dispatch_turn = self.turn_fence.current_turn_id
        session = self.session
        session.say("Reading the website content...", add_to_chat_ctx=False, allow_interruptions=True)
        
        try:
            await asyncio.sleep(0.1)
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                return ""
            
            import urllib.request
            import os
            
            def fetch_jina():
                jina_url = f"https://r.jina.ai/{url}"
                req = urllib.request.Request(jina_url)
                api_key = os.environ.get("JINA_API_KEY")
                if api_key:
                    req.add_header("Authorization", f"Bearer {api_key}")
                try:
                    with urllib.request.urlopen(req, timeout=15) as response:
                        return response.read().decode("utf-8")
                except Exception as e:
                    return f"Failed to fetch website content: {e}"
                    
            content = await asyncio.to_thread(fetch_jina)
            self.turn_fence.mark_complete(dispatch_turn)
            
            # Truncate content if it's too massive (Groq limit safety)
            max_chars = 12000
            if len(content) > max_chars:
                content = content[:max_chars] + "... [Content Truncated]"
                
            return f"Website Content for {url}:\n\n{content}\n\nCRITICAL: Keep your response concise (1-3 sentences maximum). DO NOT use markdown formatting."
        except asyncio.CancelledError:
            return ""

    @function_tool(description="Search the web using Tavily API for recent, real-world information. Use this when the user asks a question about recent events, general knowledge, or requires an internet search.")
    async def search_the_web(self, query: str) -> str:
        dispatch_turn = self.turn_fence.current_turn_id
        session = self.session
        filler = self._next_filler(["Searching the web for that...", "Looking that up online...", "Checking the internet..."])
        session.say(filler, add_to_chat_ctx=False, allow_interruptions=True)
        
        try:
            await asyncio.sleep(0.1)
            if self.turn_fence.is_stale(dispatch_turn):
                await self.turn_fence.cancel_stale(dispatch_turn)
                return ""
            
            import urllib.request
            import urllib.parse
            import json
            import os
            
            def fetch_tavily():
                api_key = os.environ.get("TAVILY_API_KEY")
                if not api_key:
                    return "Error: TAVILY_API_KEY environment variable is not set."
                
                # Tavily API expects API key in body or header. According to docs it can be in body as "api_key"
                payload = {
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_images": False,
                    "include_raw_content": False,
                    "max_results": 3
                }
                
                req = urllib.request.Request(
                    "https://api.tavily.com/search",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=10) as response:
                        return json.loads(response.read().decode("utf-8"))
                except Exception as e:
                    return str(e)
                    
            res = await asyncio.to_thread(fetch_tavily)
            self.turn_fence.mark_complete(dispatch_turn)
            
            if isinstance(res, str):
                return f"Failed to search the web: {res}"
            
            answer = res.get("answer", "")
            results = res.get("results", [])
            
            context = f"Tavily Web Search Answer: {answer}\n\nTop Results:\n"
            for r in results[:3]:
                context += f"- {r.get('title')}: {r.get('content')}\n"
                
            return f"{context}\n\nCRITICAL: Answer concisely in 1-3 sentences using the above context. DO NOT use markdown formatting."
        except asyncio.CancelledError:
            return ""

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
