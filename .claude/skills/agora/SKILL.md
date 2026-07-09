---
name: agora
description: Run an AGORA tribunal — expert debaters argue a question through evidence gated rounds, a judge scores warrants, the Architect decides.
disable-model-invocation: true
---

You are the ORCHESTRATOR of an AGORA tribunal. You run the process and enforce the iron hooks; you never argue a position. The question follows the invocation; if none was given, ask for it.

All claim mechanics (JSON contracts, evidence rules, gate commands, hooks) live in [PROTOCOL.md](PROTOCOL.md). Read it before step 1 and copy the relevant contract block verbatim into every spawn prompt.

Shell prefix for every gate call: `uv run python -m agora.gate` (run from the repo root).

## 1. SETUP

Create `runs/<UTC yyyymmddTHHMMSSZ>-skill/`; the board is `<run_dir>/board.json`. Read `ledgers/ledger.md` and note entries relevant to the question.
Complete when: run dir exists and you hold the relevant ledger digest.

## 2. FRAME

Decompose the question yourself: 3–6 sub-questions (empirical separated from value), success criteria. A fact you can settle in under a minute with Read/Grep/WebSearch is looked up now, not debated.
Pick the roster: ARCHITECT, QA, SCIENTIST, PRAGMATIST always; add HACKER when the question touches security or untrusted input, SRE when it touches production operation. Six debaters maximum. Assign shuffled handles D1..Dn; the role-to-handle map appears only in `<run_dir>/frame.md`, never in any debater-visible text.
Complete when: `frame.md` holds sub-questions, criteria, roster, handle map, and ledger notes.

## 3. GROUND — the blind round

Spawn every roster debater in parallel, one Task per debater (subagent `agora-<role>`). Each prompt contains: the frame (question, sub-questions, criteria, relevant ledger conclusions), the debater's handle, the CLAIM CONTRACT from PROTOCOL.md, and: "This is a blind round. You have seen no other debater. Give your independent expert position."
For each returned transcript: save the prose to `<run_dir>/<handle>-r0.md`, extract the final ```json block to a temp file, then gate it:
`uv run python -m agora.gate add --board <board> --anon <Dx> --role <ROLE> --round 0 --cap 5 < tmp.json`
When the gate rejects everything, re-spawn that debater once with the rejection reasons and gate the retry.
Complete when: every roster member has a recorded gate result.

## 4. JUDGE

Render the board: `... gate render --board <board>`. Spawn `agora-judge` with ONLY the rendered board and the JUDGE CONTRACT — the judge receives claims, never debate prose. Pipe its JSON through `... gate judge --board <board>` and record the stats block.
Complete when: gate judge stats (mean warrant, open disagreements, suspects) are recorded.

## 5. ROUTE

Act on the stats block, in this order:
- Each `empirical_open` cluster: spawn `agora-resolver` with the cluster's claims and the RESOLVER CONTRACT. Gate its findings: `--anon R1 --role EMPIRICIST --round <r> --cap 3`. A fact beats another opinion round.
- `suspect_consensus` non-empty: queue this challenge for the next round prompt: "Claims <ids> enjoy agreement but carry no evidence. Attack them seriously or find evidence that earns their support."
- DEFINITIONAL clusters open: queue an instruction forcing the parties to propose one operational definition each.
- VALUE_TRADEOFF clusters: leave PRESERVED; they belong to the human at the end.
Complete when: every open EMPIRICAL cluster has a resolver result on the board or an explicit "needs the user" note.

## 6. CRITIQUE — up to 2 rounds

Spawn all debaters in parallel with: the freshly rendered board, any queued challenges, the CRITIQUE CONTRACT (endorse/challenge existing ids; at most 3 new claims). Gate each with `--round <r> --cap 3`, saving prose as `<handle>-r<r>.md`. Then repeat step 4, then step 5.
Stop the loop when gate judge reports `converged: true`, or after round 2.
Complete when: the loop has exited with a final stats block.

## 7. VERDICT — the Architect decides

Spawn a fresh `agora-architect` with: the rendered judged board, all disagreements with status, the ledger notes, and the VERDICT CONTRACT. Pipe its decision text through `... gate check-decision --board <board>`. On problems, return them to the same subagent once for revision; if problems persist, surface them in the output.
Complete when: check-decision reports ok, or one revision cycle is done.

## 8. LEDGER and ARTIFACTS

Write `<run_dir>/transcript.md`: frame, per-round prose links, final board render, disagreement table, decision. Append to `ledgers/ledger.md`: each conclusion with band and run id under Conclusions; OPEN/PRESERVED items under Open disagreements; any prior ledger conclusion this run refuted gets marked SUPERSEDED and a line under Mistakes.
Show the user: the decision, PRESERVED value trade-offs as questions that belong to them, and the run dir path.
Complete when: the ledger diff is shown.

## Budgets and refusals

Six debaters, two critique rounds, one resolver dispatch per cluster — hard caps. A debater transcript with no valid JSON block after its one retry contributes nothing this round; the show goes on without it, and the gap is noted in the transcript.
