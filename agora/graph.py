"""Graph assembly (spec 9 state machine, Phase 1 subset)."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from agora.config import AgoraConfig
from agora.llm import LLM, TokenMeter
from agora.nodes import Nodes
from agora.state import DeliberationState


def build_graph(cfg: AgoraConfig) -> tuple[object, Nodes]:
    llm = LLM(cfg.budget.max_output_tokens_per_call, TokenMeter())
    nodes = Nodes(cfg, llm)

    g = StateGraph(DeliberationState)
    g.add_node("frame", nodes.frame)
    g.add_node("ground", nodes.ground)
    g.add_node("critique", nodes.critique)
    g.add_node("judge", nodes.judge)
    g.add_node("synthesize", nodes.synthesize)

    g.set_entry_point("frame")
    g.add_edge("frame", "ground")
    g.add_edge("ground", "critique")
    g.add_edge("critique", "judge")
    g.add_conditional_edges(
        "judge", nodes.should_continue,
        {"critique": "critique", "synthesize": "synthesize"},
    )
    g.add_edge("synthesize", END)

    return g.compile(), nodes
