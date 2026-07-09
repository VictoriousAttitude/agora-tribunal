"""CLI entry point.

Usage: python -m agora.cli "Should we migrate service X to gRPC?"
Writes runs/<timestamp>/transcript.md and state.json; prints verdict + costs.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agora.config import load_config
from agora.graph import build_graph
from agora.models import Claim, Disagreement


def _transcript(state: dict) -> str:
    frame = state["frame"]
    out = [f"# AGORA run\n\n## Question\n{frame.question}\n"]
    out.append("## Frame\n" + "\n".join(f"- {q}" for q in frame.sub_questions))
    out.append("\n## Reasoning\n")
    for anon, text in state.get("reasoning", {}).items():
        out.append(f"### {anon}\n\n{text}\n")
    out.append("## Claims\n")
    for c in state["claims"]:
        out.append(
            f"- `{c.id}` **{c.warrant_band}** ({c.author_anon}, {c.provenance}) "
            f"{c.statement}"
        )
    out.append("\n## Disagreements\n")
    for d in state.get("disagreements", []):
        out.append(f"- [{d.status}/{d.dclass}] {d.rationale}")
    v = state["verdict"]
    out.append(
        f"\n## Verdict (termination={v.termination}, "
        f"mean warrant={v.mean_warrant_rank:.2f})\n\n{v.decision}\n"
    )
    return "\n".join(out)


def _dump(obj):
    if isinstance(obj, (Claim, Disagreement)) or hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    raise TypeError(f"not serializable: {type(obj)}")


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python -m agora.cli "<question>"', file=sys.stderr)
        sys.exit(1)
    question = sys.argv[1]

    cfg = load_config()
    graph, nodes = build_graph(cfg)
    final = graph.invoke({"question": question})

    run_dir = Path(cfg.paths.runs_dir) / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "transcript.md").write_text(_transcript(final))
    (run_dir / "state.json").write_text(
        json.dumps(final, default=_dump, indent=2)
    )

    print(final["verdict"].decision)
    print("\n--- cost ---")
    print(nodes.llm.meter.report())
    print(f"\nartifacts: {run_dir}/")


if __name__ == "__main__":
    main()
