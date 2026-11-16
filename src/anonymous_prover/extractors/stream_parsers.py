"""Parsers for Claude stream-json output."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---- Pricing (USD per token) -----------------------------------------------
# Anthropic Sonnet-class models
_SONNET_INPUT = 3.0 / 1_000_000
_SONNET_CACHED = 0.30 / 1_000_000
_SONNET_OUTPUT = 15.0 / 1_000_000
# Anthropic Opus-class models (Opus 4.6)
_OPUS_INPUT = 5.0 / 1_000_000
_OPUS_CACHED = 0.50 / 1_000_000
_OPUS_OUTPUT = 25.0 / 1_000_000
# Anthropic Haiku-class models (Haiku 4.5)
_HAIKU_INPUT = 1.0 / 1_000_000
_HAIKU_CACHED = 0.10 / 1_000_000
_HAIKU_OUTPUT = 5.0 / 1_000_000
# OpenAI gpt-5.3-codex
_CODEX_INPUT = 1.75 / 1_000_000
_CODEX_CACHED = 0.175 / 1_000_000
_CODEX_OUTPUT = 14.0 / 1_000_000
# OpenAI gpt-5.4
_GPT54_INPUT = 2.50 / 1_000_000
_GPT54_CACHED = 0.25 / 1_000_000
_GPT54_OUTPUT = 15.0 / 1_000_000
# OpenAI gpt-5.4-mini
_GPT54MINI_INPUT = 0.75 / 1_000_000
_GPT54MINI_CACHED = 0.075 / 1_000_000
_GPT54MINI_OUTPUT = 4.50 / 1_000_000


def _get_pricing(model: str) -> tuple[float, float, float]:
    """Return (input, cached, output) per-token pricing for *model*."""
    m = model.lower() if model else ""
    # OpenAI models
    if "codex" in m or "5.3" in m:
        return _CODEX_INPUT, _CODEX_CACHED, _CODEX_OUTPUT
    if "5.4-mini" in m or "5.4-nano" in m:
        return _GPT54MINI_INPUT, _GPT54MINI_CACHED, _GPT54MINI_OUTPUT
    if "5.4" in m or "gpt-5" in m:
        return _GPT54_INPUT, _GPT54_CACHED, _GPT54_OUTPUT
    # Anthropic models
    if "opus" in m:
        return _OPUS_INPUT, _OPUS_CACHED, _OPUS_OUTPUT
    if "haiku" in m:
        return _HAIKU_INPUT, _HAIKU_CACHED, _HAIKU_OUTPUT
    return _SONNET_INPUT, _SONNET_CACHED, _SONNET_OUTPUT


@dataclass
class StreamMetrics:
    """Aggregated metrics from a Claude stream-json session."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cached_input_tokens: int = 0
    total_turns: int = 0
    tool_calls: int = 0
    model: str = ""
    # Authoritative cost from the CLI (includes sub-agent spend). Set only
    # when the CLI reported a *non-zero* value — gateways like MiroMind
    # often emit ``total_cost_usd: 0`` which we treat as "not reported" so
    # the fallback estimate takes over.
    _reported_cost_usd: float | None = None

    @property
    def cost_usd(self) -> float:
        """Return the cost reported by the CLI if available, otherwise estimate."""
        if self._reported_cost_usd is not None:
            return round(self._reported_cost_usd, 6)
        inp, cached, out = _get_pricing(self.model)
        non_cached_input = max(self.total_input_tokens - self.cached_input_tokens, 0)
        cost = (
            non_cached_input * inp
            + self.cached_input_tokens * cached
            + self.total_output_tokens * out
        )
        return round(cost, 6)

    @property
    def cost_source(self) -> str:
        """Where ``cost_usd`` came from: ``"reported"`` (CLI) or
        ``"estimated"`` (computed locally from tokens × list-price rates —
        e.g., for MiroMind / other gateway runs). ``"none"`` when no work
        was done and the value is a trivial zero."""
        if self._reported_cost_usd is not None:
            return "reported"
        if self.total_input_tokens > 0 or self.total_output_tokens > 0:
            return "estimated"
        return "none"


class StreamJsonParser:
    """Parse a ``.stream.jsonl`` file emitted by ``claude --output-format stream-json``."""

    def parse(self, stream_path: str, *, fallback_model: str = "") -> StreamMetrics:
        """Read *stream_path* line by line and return aggregated metrics."""
        metrics = StreamMetrics(model=fallback_model)

        if not os.path.exists(stream_path):
            logger.warning("Stream file not found: %s", stream_path)
            return metrics

        with open(stream_path, "r") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                raw_line = raw_line.strip()
                if not raw_line or raw_line.startswith("[TIMEOUT]"):
                    continue
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    logger.debug("Skipping non-JSON line %d", line_no)
                    continue

                self._process_event(obj, metrics)

        return metrics

    # -- internal event handlers ---------------------------------------------

    @staticmethod
    def _process_event(obj: dict, m: StreamMetrics) -> None:
        """Dispatch a single JSON event into *m*."""
        event_type = obj.get("type", "")

        # Top-level message types emitted by claude CLI
        if event_type == "assistant":
            m.total_turns += 1
            # Count tool_use blocks within the assistant message
            for block in obj.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    m.tool_calls += 1

        elif event_type == "result":
            # Final summary event — may contain per-model breakdowns
            # (modelUsage) that include sub-agent spend.
            model_usage = obj.get("modelUsage")
            if isinstance(model_usage, dict) and model_usage:
                # Aggregate tokens across all models (main + sub-agents).
                total_in = 0
                total_out = 0
                total_cached = 0
                for _model_name, mu in model_usage.items():
                    if not isinstance(mu, dict):
                        continue
                    total_in += int(mu.get("inputTokens", 0))
                    total_out += int(mu.get("outputTokens", 0))
                    total_cached += (
                        int(mu.get("cacheReadInputTokens", 0))
                        + int(mu.get("cacheCreationInputTokens", 0))
                    )
                # Replace incremental counts with authoritative totals.
                # Keep input_tokens inclusive of cache tokens.
                m.total_input_tokens = total_in + total_cached
                m.total_output_tokens = total_out
                m.cached_input_tokens = total_cached
            else:
                # Fallback: no modelUsage, use top-level usage.
                usage = obj.get("usage", {})
                cache_tokens = usage.get("cache_read_input_tokens", 0) + usage.get(
                    "cache_creation_input_tokens", 0
                )
                m.total_input_tokens += usage.get("input_tokens", 0) + cache_tokens
                m.total_output_tokens += usage.get("output_tokens", 0)
                m.cached_input_tokens += cache_tokens

            # Use CLI-reported cost (includes sub-agents) only when it's a
            # real, non-zero value. Zero almost always means "gateway
            # stripped the field" (MiroMind) rather than "free run", so
            # fall through to the token-based estimate instead.
            reported_cost = obj.get("total_cost_usd")
            if isinstance(reported_cost, (int, float)) and reported_cost > 0:
                m._reported_cost_usd = float(reported_cost)

            if not m.model:
                m.model = obj.get("model", "")

        # Streaming sub-events (for incremental token accounting)
        elif event_type == "stream_event":
            sub = obj.get("event", {})
            sub_type = sub.get("type", "")

            if sub_type == "message_start":
                msg = sub.get("message", {})
                msg_usage = msg.get("usage", {})
                cache_tokens = msg_usage.get("cache_read_input_tokens", 0) + msg_usage.get(
                    "cache_creation_input_tokens", 0
                )
                # Keep input_tokens inclusive of cache tokens.
                m.total_input_tokens += msg_usage.get("input_tokens", 0) + cache_tokens
                m.cached_input_tokens += cache_tokens
                if not m.model:
                    m.model = msg.get("model", "")

            elif sub_type == "message_delta":
                delta_usage = sub.get("usage", {})
                m.total_output_tokens += delta_usage.get("output_tokens", 0)

            elif sub_type == "content_block_start":
                block = sub.get("content_block", {})
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    m.tool_calls += 1

        # Codex stream-json events used by the runner
        elif event_type == "item.completed":
            item = obj.get("item", {})
            item_type = item.get("type", "")
            if item_type == "agent_message":
                # Count assistant emissions as turns in Codex streams.
                m.total_turns += 1
            elif item_type in {
                "command_execution",
                "mcp_tool_call",
                "custom_tool_call",
                "file_change",
            }:
                m.tool_calls += 1

        elif event_type == "turn.completed":
            usage = obj.get("usage", {})
            if isinstance(usage, dict):
                m.total_input_tokens += int(usage.get("input_tokens", 0) or 0)
                m.total_output_tokens += int(usage.get("output_tokens", 0) or 0)
                m.cached_input_tokens += int(usage.get("cached_input_tokens", 0) or 0)

        # Best-effort fallback for non-Claude JSONL streams (e.g. codex exec --json)
        if event_type not in {
            "assistant",
            "result",
            "stream_event",
            "item.completed",
            "turn.completed",
            "thread.started",
            "turn.started",
            "item.started",
        }:
            usage = obj.get("usage")
            if isinstance(usage, dict):
                m.total_input_tokens += int(
                    usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
                )
                m.total_output_tokens += int(
                    usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
                )
                m.cached_input_tokens += int(
                    usage.get("cached_input_tokens", 0) or 0
                )
                if not m.model and usage.get("model"):
                    m.model = str(usage.get("model", ""))

            message = obj.get("message")
            if isinstance(message, dict):
                if message.get("role") == "assistant":
                    m.total_turns += 1
                for block in message.get("content", []):
                    if isinstance(block, dict) and block.get("type") in {"tool_use", "tool_call"}:
                        m.tool_calls += 1
