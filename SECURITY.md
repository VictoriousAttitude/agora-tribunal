# AGORA security: residual risks

Documented per tribunal run 20260711T160712Z-skill. Band=VERIFIED on all three.

## 1. Bash(*) is session-wide

`settings.local.json` grants `Bash(*)` to the entire session. Debater agent frontmatter omits Bash from its `tools:` field, but this is advisory — the model may still invoke Bash if prompted. A prompt-injected debater could execute arbitrary shell commands including direct writes to board.json or ledger.md.

**Mitigation**: Post-run audit — diff board.json claim IDs against gate add stdout logs. Any ID present in board.json but absent from gate logs indicates a bypass.

**Blocked fix**: Claude Code does not support `disallowedTools` that overrides session-wide allow.

## 2. Write(runs/**) and Write(ledgers/**) bypass gate hooks

board.json lives at `runs/<timestamp>/board.json`, matching `Write(runs/**)`. ledger.md matches `Write(ledgers/**)`. A prompt-injected debater can write directly to either file, bypassing all H1-H9 gate hooks.

**Mitigation**: Ledger damage is cosmetic — entries are human-visible plaintext, reviewed at SETUP, and caught by git diff. Board damage is detectable by the post-run audit above.

**Blocked fix**: Claude Code has no per-agent Write path scoping. The `tools:` frontmatter field is a name allowlist only.

## 3. WEAK claims pass check-decision

H9 hard-blocks CONTESTED claims and claims inside OPEN disagreements from carrying a decision. But WEAK claims (including ASSERTION-capped injected claims) produce only an UNSCRUTINIZED warning — `ok` remains `true`. A prompt-injected WEAK claim cited in the decision will not bounce.

**Mitigation**: The scrutiny cycle (SKILL.md step 7) spawns adversarial debaters to attack UNSCRUTINIZED claims before the decision finalizes. One cycle maximum.
