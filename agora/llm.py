"""Anthropic SDK wrapper with per-role token metering (spec 13.4).

Two call shapes:
- complete(): free-form text (pass 1 of debater turns, synthesizer prose).
- structured(): forced tool use returning the tool input dict (claim
  extraction, judge assessments, frame output). Forcing tool_choice makes
  the model emit schema-valid JSON instead of prose.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import anthropic


@dataclass
class TokenMeter:
    """Accumulates usage per label (role name or meta component)."""
    input_tokens: dict[str, int] = field(default_factory=dict)
    output_tokens: dict[str, int] = field(default_factory=dict)

    def add(self, label: str, usage: Any) -> None:
        self.input_tokens[label] = self.input_tokens.get(label, 0) + usage.input_tokens
        self.output_tokens[label] = self.output_tokens.get(label, 0) + usage.output_tokens

    @property
    def total(self) -> int:
        return sum(self.input_tokens.values()) + sum(self.output_tokens.values())

    def report(self) -> str:
        lines = ["label            input   output"]
        for label in sorted(set(self.input_tokens) | set(self.output_tokens)):
            i = self.input_tokens.get(label, 0)
            o = self.output_tokens.get(label, 0)
            lines.append(f"{label:<15} {i:>7} {o:>8}")
        lines.append(f"{'TOTAL':<15} {sum(self.input_tokens.values()):>7} "
                     f"{sum(self.output_tokens.values()):>8}")
        return "\n".join(lines)


class LLM:
    def __init__(self, max_output_tokens: int, meter: TokenMeter | None = None):
        self.client = anthropic.Anthropic()
        self.max_output_tokens = max_output_tokens
        self.meter = meter or TokenMeter()

    def complete(self, *, model: str, system: str, user: str, label: str) -> str:
        resp = self.client.messages.create(
            model=model,
            max_tokens=self.max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        self.meter.add(label, resp.usage)
        return "".join(b.text for b in resp.content if b.type == "text")

    def structured(
        self, *, model: str, system: str, user: str, tool: dict, label: str,
        max_tokens: int | None = None,
    ) -> dict:
        """Force a single tool call and return its input payload."""
        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens or self.max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        self.meter.add(label, resp.usage)
        if resp.stop_reason == "max_tokens":
            raise RuntimeError(
                f"structured output truncated at max_tokens (label={label}); "
                "raise the cap for this call"
            )
        for block in resp.content:
            if block.type == "tool_use":
                return block.input
        raise RuntimeError(f"forced tool_choice returned no tool_use block (label={label})")
