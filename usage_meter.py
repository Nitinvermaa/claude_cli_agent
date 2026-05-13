from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# USD per million tokens. Keep this map easy to update.
MODEL_PRICING_PER_MTOKENS: dict[str, dict[str, float]] = {
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0},
    "claude-opus-4-1-20250805": {"input": 15.0, "output": 75.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.8, "output": 4.0},
}


@dataclass
class UsageSnapshot:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


@dataclass
class SessionUsageMeter:
    requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_estimated_usd: float = 0.0
    unknown_usage_requests: int = 0

    def add(self, snapshot: UsageSnapshot | None, model: str) -> float | None:
        self.requests += 1
        if snapshot is None or snapshot.input_tokens is None or snapshot.output_tokens is None:
            self.unknown_usage_requests += 1
            return None

        self.total_input_tokens += snapshot.input_tokens
        self.total_output_tokens += snapshot.output_tokens
        request_cost = estimate_cost_usd(model, snapshot.input_tokens, snapshot.output_tokens)
        if request_cost is not None:
            self.total_estimated_usd += request_cost
        return request_cost

    def session_report(self) -> str:
        lines = [
            f"Session requests: {self.requests}",
            f"Session input tokens: {self.total_input_tokens}",
            f"Session output tokens: {self.total_output_tokens}",
            f"Session total tokens: {self.total_input_tokens + self.total_output_tokens}",
            f"Session estimated spend (USD): ${self.total_estimated_usd:.6f}",
        ]
        if self.unknown_usage_requests:
            lines.append(
                "Requests without usage metadata: "
                f"{self.unknown_usage_requests} (SDK/provider did not expose token details)"
            )
        return "\n".join(lines)


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj

    out: dict[str, Any] = {}
    for key in dir(obj):
        if key.startswith("_"):
            continue
        value = getattr(obj, key, None)
        if callable(value):
            continue
        out[key] = value
    return out


def _first_int(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def extract_usage_snapshot(result_message: Any) -> UsageSnapshot | None:
    if result_message is None:
        return None

    usage_obj = getattr(result_message, "usage", None)
    usage = _to_dict(usage_obj)

    result_obj = getattr(result_message, "result", None)
    if not usage and isinstance(result_obj, dict):
        usage = _to_dict(result_obj.get("usage"))

    input_tokens = _first_int(
        usage.get("input_tokens"),
        usage.get("prompt_tokens"),
        usage.get("inputTokens"),
    )
    output_tokens = _first_int(
        usage.get("output_tokens"),
        usage.get("completion_tokens"),
        usage.get("outputTokens"),
    )
    cache_creation = _first_int(
        usage.get("cache_creation_input_tokens"),
        usage.get("cacheCreationInputTokens"),
    )
    cache_read = _first_int(
        usage.get("cache_read_input_tokens"),
        usage.get("cacheReadInputTokens"),
    )

    if input_tokens is None and output_tokens is None and not usage:
        return None

    return UsageSnapshot(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
        raw=usage,
    )


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    pricing = MODEL_PRICING_PER_MTOKENS.get(model)
    if pricing is None:
        return None
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def request_report(
    model: str,
    snapshot: UsageSnapshot | None,
    estimated_cost: float | None,
    max_output_tokens: int,
    max_session_usd: float | None,
) -> str:
    lines = [
        f"Model: {model}",
        f"Configured output token limit per request: {max_output_tokens}",
    ]
    if max_session_usd is not None:
        lines.append(f"Configured session budget limit (USD): ${max_session_usd:.2f}")

    if snapshot is None:
        lines.append("Request usage: unavailable (provider/SDK did not return usage metadata)")
        return "\n".join(lines)

    lines.append(f"Request input tokens: {snapshot.input_tokens if snapshot.input_tokens is not None else 'unknown'}")
    lines.append(f"Request output tokens: {snapshot.output_tokens if snapshot.output_tokens is not None else 'unknown'}")
    lines.append(f"Request total tokens: {snapshot.total_tokens if snapshot.total_tokens is not None else 'unknown'}")
    if snapshot.cache_creation_input_tokens is not None:
        lines.append(f"Cache creation input tokens: {snapshot.cache_creation_input_tokens}")
    if snapshot.cache_read_input_tokens is not None:
        lines.append(f"Cache read input tokens: {snapshot.cache_read_input_tokens}")
    if estimated_cost is not None:
        lines.append(f"Request estimated spend (USD): ${estimated_cost:.6f}")
    else:
        lines.append("Request estimated spend (USD): unknown (model pricing not configured)")
    return "\n".join(lines)
