"""Model factory, usage and cost meter, budget caps, and error mapping.

Provider: Claude Haiku 5.5 with ANTHROPIC_API_KEY, else gpt-6-luna with OPENAI_API_KEY (chosen in config.py). This is a deliberate exception to the class default
(gpt-6-luna through Portkey), chosen by the project owner. Haiku 5.5 rules kept here: no temperature, top_p or top_k,
no thinking budgets, no assistant prefill; effort "low" for the simple agents.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from . import config

# USD per million tokens. Haiku 5.5: Anthropic list price for prompts up to 100K tokens (2026-11-20);
# cache reads are 0.1x input, 5-minute cache writes 1.25x input. gpt-6-luna (the OPENAI_API_KEY path) from the full app's data/prices.json;
# OpenAI has no cache-write charge, so any tokens reported as cache writes are priced as plain input.
PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-5-5": {"input": 0.10, "cached": 0.01, "cache_write": 0.125, "output": 0.50},
    "gpt-6-luna": {"input": 0.10, "cached": 0.01, "cache_write": 0.10, "output": 0.50},
}
FALLBACK_PRICE = PRICES["claude-haiku-5-5"]
REQUEST_TIMEOUT_S = 30.0     # one model request
AGENT_TIMEOUT_S = 60.0       # one agent run, all its requests and tools
SPECIALIST_TIMEOUT_S = 12.0  # one specialist's writing (typical 2-4 s); past it the specialist's template is used
PLAN_AI_SECONDS = 24.0       # a plan's model calls all finish within this; later ones use templates (tools take ~1 s more)
MIN_AI_SECONDS = 3.0         # a model call needs at least this much of the plan's time left to start

AI_UNAVAILABLE = "The AI service is not available right now. The numbers below come from the app's own tools."
BUDGET_STOP = "This run reached its spending limit, so the AI stopped. The numbers below come from the app's own tools."


class AIUnavailable(Exception):
    """The model could not be reached (no key, bad key, rate limit, network)."""

    def __init__(self, reason: str = "unavailable"):
        self.reason = reason
        super().__init__(reason)


class BudgetExceeded(Exception):
    """A hard spending cap would be passed."""


def price_for(model: str) -> dict[str, float]:
    return PRICES.get(model, FALLBACK_PRICE)


def cost_usd(model: str, input_uncached: int, cached: int, cache_write: int, output: int) -> float:
    p = price_for(model)
    return (input_uncached * p["input"] + cached * p["cached"] + cache_write * p["cache_write"] + output * p["output"]) / 1e6


# ------------------------------------------------------------------ per-agent limits (they make the caps hard)
@dataclass(frozen=True)
class AgentLimits:
    max_tokens: int = 1500          # per response
    requests: int = 4               # model calls per agent run
    input_tokens: int = 24000       # whole agent run
    output_tokens: int = 4000       # whole agent run (thinking counts here)

    def worst_case_usd(self, model: str) -> float:
        p = price_for(model)
        # one request can overshoot the token limits before PydanticAI stops it
        return ((self.input_tokens + 8000) * max(p["input"], p["cache_write"]) + (self.output_tokens + self.max_tokens) * p["output"]) / 1e6


SIMPLE = AgentLimits()
LEAD = AgentLimits(max_tokens=3000, requests=4, input_tokens=30000, output_tokens=8000)


def make_model():
    """The one place that builds the model. Raises AIUnavailable when there is no key."""
    settings = config.get_settings()
    if not settings.has_key:
        raise AIUnavailable("no_key")
    import os

    if settings.provider == "openai":
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider

        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), timeout=REQUEST_TIMEOUT_S, max_retries=1)
        return OpenAIResponsesModel(settings.model, provider=OpenAIProvider(openai_client=client))

    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"].strip(), timeout=REQUEST_TIMEOUT_S, max_retries=1)
    return AnthropicModel(settings.model, provider=AnthropicProvider(anthropic_client=client))


def model_settings(effort: Literal["low", "medium", "high"] = "low", limits: AgentLimits = SIMPLE) -> dict[str, Any]:
    """Anthropic: effort only (no sampling parameters, no thinking budget), prompt caching on.
    OpenAI (gpt-6-luna, a reasoning model): the same effort as reasoning effort and a prompt-cache key; no temperature; the
    output cap is left to the usage limits, because reasoning tokens count against max_tokens."""
    if config.get_settings().provider == "openai":
        return {"openai_reasoning_effort": effort, "openai_prompt_cache_key": "enough-lite"}
    return {
        "max_tokens": limits.max_tokens,
        "anthropic_effort": effort,
        "anthropic_cache_instructions": True,
        "anthropic_cache_tool_definitions": True,
        "anthropic_cache_messages": True,
    }


def usage_limits(limits: AgentLimits):
    from pydantic_ai.usage import UsageLimits

    return UsageLimits(request_limit=limits.requests, input_tokens_limit=limits.input_tokens, output_tokens_limit=limits.output_tokens)


def map_error(exc: BaseException) -> AIUnavailable | None:
    """Map provider failures to AIUnavailable. Returns None for errors that are not about reaching the model."""
    if isinstance(exc, AIUnavailable):
        return exc
    try:
        from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UsageLimitExceeded
    except ImportError:  # pragma: no cover
        return None
    if isinstance(exc, ModelHTTPError):
        code = exc.status_code
        if code in (401, 403):
            return AIUnavailable("auth")
        if code == 429:
            return AIUnavailable("rate_limited")
        if code >= 500:
            return AIUnavailable("provider_error")
        return AIUnavailable(f"http_{code}")
    if isinstance(exc, UsageLimitExceeded):
        return AIUnavailable("agent_limit")
    if isinstance(exc, ModelAPIError):
        return AIUnavailable("connection")
    name = type(exc).__name__
    if any(k in name for k in ("Connect", "Timeout", "Network")):
        return AIUnavailable("connection")
    return None


# ------------------------------------------------------------------ meter
@dataclass
class UsageEntry:
    run_id: str
    session: str
    agent: str
    model: str
    input_tokens: int          # uncached input
    cached_tokens: int         # cache reads
    cache_write_tokens: int
    output_tokens: int
    requests: int
    cost_usd: float
    seconds: float
    ok: bool
    note: str = ""
    at: float = field(default_factory=time.time)

    @property
    def tokens(self) -> dict[str, int]:
        return {"input": self.input_tokens, "cached": self.cached_tokens, "output": self.output_tokens}


class Meter:
    """Records every agent run and enforces the caps. One instance per process."""

    def __init__(self):
        self.entries: list[UsageEntry] = []
        self.hidden: set[int] = set()        # entries cleared from a session's log; they still count toward the caps
        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self.entries.clear()
            self.hidden.clear()

    def clear_history(self, session: str) -> int:
        """Hide a session's entries from its cost log. The spend counter is untouched."""
        with self._lock:
            ids = {id(e) for e in self.entries if e.session == session} - self.hidden
            self.hidden |= ids
            return len(ids)

    def spent(self, *, run_id: str | None = None, session: str | None = None) -> float:
        with self._lock:
            return sum(e.cost_usd for e in self.entries
                       if (run_id is None or e.run_id == run_id) and (session is None or e.session == session))

    def check(self, run_id: str, session: str, worst_case: float) -> None:
        """Raise BudgetExceeded unless the next agent run fits under every cap even in its worst case."""
        s = config.get_settings()
        if self.spent(run_id=run_id) + worst_case > s.run_budget_usd:
            raise BudgetExceeded("run")
        if self.spent(session=session) + worst_case > s.session_budget_usd:
            raise BudgetExceeded("session")
        if self.spent() + worst_case > s.total_budget_usd:
            raise BudgetExceeded("total")

    def record(self, run_id: str, session: str, agent: str, model: str, usage: Any, seconds: float, ok: bool = True, note: str = "") -> UsageEntry:
        """usage: a PydanticAI RunUsage (input_tokens includes cache reads and writes) or None."""
        inp = int(getattr(usage, "input_tokens", 0) or 0)
        cr = int(getattr(usage, "cache_read_tokens", 0) or 0)
        cw = int(getattr(usage, "cache_write_tokens", 0) or 0)
        out = int(getattr(usage, "output_tokens", 0) or 0)
        req = int(getattr(usage, "requests", 0) or 0)
        unc = max(0, inp - cr - cw)
        e = UsageEntry(run_id, session, agent, model, unc, cr, cw, out, req, round(cost_usd(model, unc, cr, cw, out), 6), round(seconds, 2), ok, note)
        with self._lock:
            self.entries.append(e)
        _append_log(e)
        return e

    def summary(self, session: str | None = None) -> dict[str, Any]:
        with self._lock:
            rows = [e for e in self.entries if (session is None or e.session == session) and (session is None or id(e) not in self.hidden)]
        by_agent: dict[str, dict[str, Any]] = {}
        for e in rows:
            a = by_agent.setdefault(e.agent, {"agent": e.agent, "runs": 0, "input": 0, "cached": 0, "cache_write": 0, "output": 0, "cost_usd": 0.0, "seconds": 0.0})
            a["runs"] += 1
            a["input"] += e.input_tokens
            a["cached"] += e.cached_tokens
            a["cache_write"] += e.cache_write_tokens
            a["output"] += e.output_tokens
            a["cost_usd"] = round(a["cost_usd"] + e.cost_usd, 6)
            a["seconds"] = round(a["seconds"] + e.seconds, 2)
        s = config.get_settings()
        return {
            "model": s.model,
            "prices_per_million": price_for(s.model),
            "budget": {"run_usd": s.run_budget_usd, "session_usd": s.session_budget_usd, "total_usd": s.total_budget_usd},
            "total_usd": round(sum(e.cost_usd for e in rows), 6),
            "total_tokens": sum(e.input_tokens + e.cached_tokens + e.cache_write_tokens + e.output_tokens for e in rows),
            "by_agent": list(by_agent.values()),
            "entries": [asdict(e) for e in rows[-200:]],
        }


def _append_log(e: UsageEntry) -> None:
    """Token counts only; no prompts, no keys."""
    if not config.get_settings().write_run_log:
        return
    try:
        config.RUNS_DIR.mkdir(exist_ok=True)
        with open(config.RUNS_DIR / "usage.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(e)) + "\n")
    except OSError:
        pass


METER = Meter()
