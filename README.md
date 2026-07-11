# AGORA

Multi-agent deliberation engine with evidence gated reasoning.

Core thesis: **deliberate wide, execute narrow.** A roster of expert debaters argues a question through structured rounds, a non-participant judge scores every claim by its evidence, and a single Architect commits to one decision. Confidence is never self-reported — warrant is derived mechanically from provenance, and unsupported consensus gets challenged instead of trusted.

Full design: `specs.txt`. Run history and standing conclusions: `ledgers/ledger.md`.

## Two ways to run it

| | Mode B (skill) | Mode A (lab) |
|---|---|---|
| Entry point | `/agora` inside Claude Code | `python -m agora.cli` |
| Billing | subscription, $0 marginal | API key, per token |
| Roster | 4 core + up to 2 conditional debaters | 3 debaters (config.yaml) |
| Resolvers, scrutiny cycles | yes | not yet |
| Use for | real questions, daily work | engine development, evals |

Mode B is the daily driver. Mode A exists to develop and benchmark the engine.

## Mode B: the /agora skill

Inside a Claude Code session in this repo:

```
/agora Should the ledger move from markdown to SQLite now that runs are accumulating?
```

The orchestrator then runs the 8-step tribunal (`.claude/skills/agora/SKILL.md`):

1. **SETUP** — creates `runs/<timestamp>-skill/`, reads the ledger for prior conclusions.
2. **FRAME** — decomposes the question into sub-questions, picks the roster. ARCHITECT, QA, SCIENTIST, PRAGMATIST always; HACKER joins if the question touches security, SRE if it touches production operation. Debaters get shuffled anonymous handles (D1..Dn) so nobody argues from authority.
3. **GROUND** — a blind round: every debater states its independent position without seeing the others. Claims are piped through the gate, which strips fake evidence and caps unsupported claims at WEAK.
4. **JUDGE** — a separate judge sees only the claim board (never the prose) and assigns warrant bands.
5. **ROUTE** — open empirical disputes go to a resolver that runs commands and fetches sources; a fact beats another opinion round. Confident-but-evidence-free consensus gets queued for attack.
6. **CRITIQUE** — up to 2 rounds of endorse/challenge/new-evidence, re-judged each time.
7. **VERDICT** — a fresh Architect drafts a decision. The gate bounces drafts that lean on contested or never-reviewed claims; load-bearing claims nobody attacked trigger one forced scrutiny cycle first.
8. **LEDGER** — the decision, its warrant, and any surviving disagreements are appended to `ledgers/ledger.md` so future runs do not relearn them.

You get back: the decision with cited claim ids, any value trade-offs that are yours to override, and the run directory with full transcripts.

### Asking good questions

The tribunal earns its cost on questions with real trade-offs and checkable facts:

```
/agora Adopt LangGraph for orchestration or keep the prompted procedure plus gate CLI?
/agora Is the Write-path around the gate an actual attack surface, and what is the cheapest hardening?
/agora Store run artifacts per-run or consolidate into one append-only log?
```

Do not use it for questions that are cheaper to just answer:

- Anything settled by one `Read`/`Grep`/`WebSearch` — the FRAME step will look it up instead of debating it, so you paid tribunal overhead for a lookup.
- Pure taste with no consequences ("tabs or spaces").
- Questions where you have already decided and want validation — the roster will happily attack your premise.

### Hard budgets

Six debaters, two critique rounds, one resolver dispatch per dispute cluster. A debater that produces no valid claims after one retry is dropped for the round. These caps are not tunable per run by design.

## Mode A: the Python engine

```bash
export ANTHROPIC_API_KEY=...
uv sync
uv run python -m agora.cli "Should we migrate service X to gRPC?"
```

Prints the verdict plus a token/cost report, and writes `runs/<timestamp>/transcript.md` and `state.json`. Roster, model tiers, budgets, and convergence thresholds live in `config.yaml`. One round with the default roster is roughly 12 LLM calls.

```bash
uv run pytest          # models + gate tests
uv run ruff check .    # lint
```

## The gate CLI

Both modes funnel every claim through the same mechanical enforcement layer. It is scriptable on its own:

```bash
# Add a debater's claims to a board (validates, strips, caps; prints accept/reject report)
uv run python -m agora.gate add --board runs/x/board.json \
    --anon D1 --role QA --round 0 --cap 5 < claims.json

# Render the board for a judge or architect (claims + disagreement table, no prose)
uv run python -m agora.gate render --board runs/x/board.json

# Apply a judge's assessments (bands clamped to provenance ceilings)
uv run python -m agora.gate judge --board runs/x/board.json < judge.json

# Check a decision draft against the board (bounces contested/unknown ids, warns on
# claims no adversary reviewed, requires preserved trade-offs to be disclosed)
uv run python -m agora.gate check-decision --board runs/x/board.json < decision.md
```

A claims payload looks like:

```json
{"claims": [{
  "statement": "SQLite adds a build dependency the current workflow never touches",
  "claim_type": "EMPIRICAL",
  "provenance": "TOOL_RESULT",
  "evidence": [{"kind": "STATIC_ANALYSIS",
                "ref": "rg -c sqlite3 agora/",
                "digest": "0 matches across 9 modules"}],
  "depends_on": [], "contradicts": []
}]}
```

### What the gate enforces (H1..H10)

- Evidence-less provenance collapses to ASSERTION; ASSERTION is capped at WEAK no matter how confidently stated (H1, H2).
- Evidence needs a real digest — at least 12 chars of actual output. Placeholders are stripped (H5).
- Judge bands are clamped to provenance ceilings: only TOOL_RESULT can reach VERIFIED (H2, H6).
- Confidence percentages are flagged and ignored; warrant comes from evidence, never self-report (H7).
- Agreement without evidence is marked SUSPECT_CONSENSUS and gets attacked, not trusted (H8).
- Decisions citing contested, unknown, or still-disputed claim ids bounce back for revision (H9).
- Every preserved value trade-off must be named in the decision by its `dis` id — no silent value calls (H10).

The consequence: inflating provenance gains nothing (it gets clamped), and honest ASSERTION costs nothing (expert judgment is still admitted, just weighted as such).

## Repo layout

```
agora/               engine: models, gate, LangGraph nodes, CLI
  gate.py            mechanical hook enforcement (shared by both modes)
.claude/skills/agora SKILL.md (orchestration) + PROTOCOL.md (contracts, hooks)
.claude/agents/      8 debater/judge/resolver agent definitions
prompts/             Mode A prompt templates
ledgers/ledger.md    conclusions, open disagreements, mistakes (append only)
evals/candidates.md  benchmark tasks with ground truth verdicts
runs/                per-run artifacts (boards, transcripts, decisions)
specs.txt            full design spec (v1.0)
```

## Reading a finished run

Each `runs/<id>/` contains `frame.md` (sub-questions, roster, handle map), `board.json` (the machine state), per-debater transcripts (`D1-r0.md`, ...), and `transcript.md` (the human-readable record: frame, rounds, final board, disagreement table, decision). When a run's conclusion later turns out wrong, it is marked SUPERSEDED in the ledger and logged under Mistakes — the ledger never silently rewrites history.
