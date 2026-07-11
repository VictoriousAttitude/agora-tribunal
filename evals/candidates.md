# Eval candidate tasks (target: 10)

Brain-dump past technical decisions here, especially ones that went wrong.
Each becomes an eval task: AGORA deliberates it blind, we compare the verdict
against what actually happened.

Best candidates are decisions where:
- the outcome is now known (right or wrong, with evidence)
- reasonable experts disagreed at the time
- the wrong choice was driven by an unexamined assumption

Template per task:

## <short title>
- Question as it stood then (no hindsight leaking into the wording):
- Context the debaters get:
- What was decided:
- What actually happened:
- Ground truth verdict (what the right call was, and why):

---

## 1. Coded graph orchestration vs prompted procedure for multi-agent debate

- Question as it stood then (no hindsight leaking into the wording):
  For a multi-agent deliberation system with 6 debaters, a judge, a resolver, and an architect — should the orchestrator be a programmatic state machine (LangGraph with typed state, conditional edges, deterministic routing) or a prompted procedure (a markdown skill file the operator follows step by step, with mechanical hooks enforced by a separate gate CLI)?

- Context the debaters get:
  - The system has two classes of rules: "hard" rules (evidence validation, provenance ceilings, ID checks, cap enforcement) and "soft" rules (output format, terse style, transcript saving, role differentiation).
  - Hard rules are enforced by a gate CLI regardless of orchestration approach (the gate validates all claims before writing to the board).
  - The coded approach (LangGraph): Python engine with typed state (TypedDict), conditional edges for routing (terminate on convergence, re-debate otherwise), compiled graph. 9 modules, ~800 lines. Deterministic topology. Testable in isolation. Requires API key ($0.11/run with haiku models).
  - The prompted approach: A 70-line markdown file (SKILL.md) describing 8 steps. The operator (Claude Code in skill mode) follows the steps, spawning subagents and piping output through the same gate CLI. Zero infrastructure. Subscription-billed ($0 marginal). Operator can improvise routing mid-run.
  - The system is single-user, single-process, sequential (no concurrent runs).
  - Industry context: LangGraph, CrewAI, AutoGen, and similar frameworks are the standard approach for multi-agent orchestration as of mid-2026.

- What was decided:
  Both were built. Mode A (LangGraph) was built first as the "real" implementation. Mode B (SKILL.md) was built second as an experiment for daily use.

- What actually happened:
  Mode B produced 3 successful tribunal runs including a full 6-debater roster with resolver dispatch, scrutiny cycle, and ERROR class adjudication. All mechanical guarantees (H1-H10) held in every run. Mode A was smoke-tested once and never used for real work. The prompted procedure achieved identical reliability because the hard rules live in gate.py (code) regardless of orchestration method — the framework added no guarantees the gate didn't already enforce.

- Ground truth verdict (what the right call was, and why):
  Prompted procedure wins for a single-user, operator-is-the-model system. The unexamined assumption: "reliable multi-agent behavior requires programmatic orchestration." This is false when (a) the hard rules are already in a separate enforcement layer (the gate), and (b) the operator is a frontier model capable of following a procedure. Coded orchestration is warranted only when the operator is untrusted or the system runs unattended.

## 2. Elicited confidence vs derived warrant bands

- Question as it stood then (no hindsight leaking into the wording):
  For an AI deliberation system where multiple agents make claims — should the system ask each agent to self-report its confidence (e.g., "I'm 85% sure") or should confidence be derived mechanically from the evidence attached to each claim?

- Context the debaters get:
  - Models from Anthropic and OpenAI publish calibration curves showing reasonable self-calibration on factual questions.
  - Superforecasting and prediction markets rely on elicited confidence successfully.
  - LLM agents are known to be sycophantic and to inflate confidence under adversarial prompting.
  - The alternative (derived warrant) works as follows: each claim declares provenance (TOOL_RESULT, RETRIEVED_SOURCE, EXTERNAL_CITATION, ASSERTION). A mechanical gate strips evidence with placeholder digests, collapses evidence-less provenance to ASSERTION, and caps warrant bands by provenance ceiling (ASSERTION<=WEAK, CITATION/SOURCE<=STRONG, TOOL_RESULT<=VERIFIED). A judge then assigns bands within these ceilings based on evidence quality.
  - The system has 6 debaters arguing adversarially — they are incentivized to sound confident regardless of evidence quality.
  - There is no "skin in the game" mechanism for LLM agents (no cost to being wrong, no reward for calibration).

- What was decided:
  Derived warrant bands with provenance ceilings. Confidence language is mechanically flagged (H7) and never honored.

- What actually happened:
  Across 3 runs, every ASSERTION claim was mechanically capped at WEAK regardless of how authoritatively stated. In run 3, claim 9d22b9ddb79b would have self-reported high confidence (the agent had read the file and quoted it) but the file changed mid-run — the evidence digest no longer matched reality. The mechanical system caught the error through adversarial scrutiny checking evidence against current state, not through the agent being humble. Six agents all independently produced confident-sounding ASSERTION claims that the gate correctly demoted to WEAK without asking them how sure they were.

- Ground truth verdict (what the right call was, and why):
  Derived warrant wins. The unexamined assumption in elicited confidence: "an agent that is confident has good reason to be." In practice, confidence tracks familiarity with the question, not correctness of the answer. Mechanical derivation from evidence creates an incentive to gather evidence rather than assert harder. The adversarial structure (6 debaters challenging each other) makes self-reported confidence even less reliable — agents have reason to inflate.

## 3. Many specialized agents vs fewer generalist agents

- Question as it stood then (no hindsight leaking into the wording):
  For a deliberation system with a fixed token budget — is it better to have 6 specialized debaters (ARCHITECT, HACKER, SRE, SCIENTIST, QA, PRAGMATIST) each seeing the question from one constrained angle, or 2-3 generalist debaters asked to consider all angles with deeper reasoning per agent?

- Context the debaters get:
  - The system has a hard cap of 6 debaters maximum. Each gets 5 claims (ground) or 3 claims (critique) per round.
  - Specialized agents have a "leading words" constraint: HACKER leads with "attack surface", ARCHITECT leads with "trade-offs", SRE leads with "failure modes", etc.
  - Generalist agents would get a combined prompt: "Consider security, reliability, architecture, testing, cost, and scientific rigor."
  - Token budget is roughly fixed either way (same number of total claims on the board).
  - The roster is conditional: HACKER only activates for security-relevant questions, SRE only for production-operation questions. Core roster is always ARCHITECT + QA + SCIENTIST + PRAGMATIST (4 agents).
  - Real expert panels (RAND, DARPA red teams, medical boards) use domain specialists, not generalists.
  - However, individual domain experts in the real world still have broad knowledge of adjacent fields.
  - Research on ensemble methods suggests diversity of approach matters more than individual depth beyond a threshold.

- What was decided:
  Specialized agents with conditional roster expansion. 4 core + up to 2 domain specialists based on question topic.

- What actually happened:
  Run 2 (4 debaters: ARCHITECT, QA, SCIENTIST, PRAGMATIST) deliberated the ledger storage question successfully but missed security implications entirely (no one mapped the Write-path bypass). Run 3 (6 debaters: added HACKER + SRE) on the hardening question produced genuinely non-overlapping findings. D1 (HACKER) mapped attack paths that no other role raised. D3 (SRE) identified crash recovery gaps from an ops perspective. D4 (SCIENTIST) applied the Rule of Two framework from security research. D6 (PRAGMATIST) bounded cost/benefit. The Write-path bypass was caught immediately by the HACKER role. The combined coverage of 6 specialists was strictly broader than what 4 produced — no single generalist prompt raised all four framings (attack surface + crash recovery + academic framework + cost bound) in the same response.

- Ground truth verdict (what the right call was, and why):
  Specialized wins when the question touches multiple domains. The unexamined assumption in the generalist model: "a smart model will naturally consider all angles." In practice, a single prompt biases toward the first framing the model locks onto. Role-forcing mechanically guarantees coverage of angles that a generalist might never reach. The conditional roster design is correct: questions that don't touch security don't need a HACKER wasting a claim slot on "the attack surface is negligible."
## 4.
## 5.
## 6.
## 7.
## 8.
## 9.
## 10.
