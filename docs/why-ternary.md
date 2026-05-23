# Why Ternary — Four Case Studies

Every real-world system encounters uncertainty. Binary logic (true/false) cannot express it; you either force a choice or build workarounds. Sanyan's three-valued logic (true / maybe / false) follows Kleene strong logic — `maybe` propagates correctly through any expression.

## Case 1: Circuit Simulator — Correctness by Construction

**File:** `examples/circuit_sim.san`

A verification circuit `(A AND B) OR (NOT A)` — 9 possible input combinations. With binary logic, the truth table is:

| A | B | Output |
|---|---|---|
| 0 | 0 | 1 |
| 0 | 1 | 1 |
| 1 | 0 | 0 |
| 1 | 1 | 1 |

In Sanyan, every Kleene triple (`true`, `maybe`, `false` mapped as 1, 0, -1):

| A | B | Output |
|---|---|---|
| true | true | 1 |
| true | false | -1 |
| true | maybe | 0 |
| false | true | 1 |
| false | false | 1 |
| false | maybe | 1 |
| maybe | true | 0 |
| maybe | false | 0 |
| maybe | maybe | 0 |

When A=maybe and B=true, the output is **maybe** — the circuit correctly says "I don't know." A binary language would need custom trit enums and 9-branch pattern matching for the same result. Sanyan's `AND`/`OR`/`NOT` are built-in Kleene operators; the verification circuit is a one-liner `(A AND B) OR (NOT A)` with zero bugs.

10-input circuit: 3^10 = 59049 combinations, all semantically correct by construction.

## Case 2: Data Cleaning Pipeline — NULL Is Not Zero

**File:** `examples/data_cleaning.san`

A user-scoring function checks 4 fields (phone, email, ID, address) marked as `verified=True`, `verified=False`, or `verified=Maybe`. The ternary scorer skips `Maybe` fields and reports the score based only on verified data. When all 4 fields are unverified, it returns **maybe** — "I don't have enough data."

The Python `None` equivalent cannot distinguish "data insufficient" from "score is zero." It returns 0 in the all-unverified case. A downstream system might deny credit, flag for manual review, or silently pass a misleading score — all because `None` is indistinguishable from `0`.

| All 4 fields unverified | Ternary output | Python None output |
|---|---|---|
| Meaning | "data insufficient" | 0 (looks like "poor score") |
| Downstream action | request more data | proceed with misleading value |

Kleene propagation guarantees: `maybe AND maybe = maybe`. Uncertainty composes correctly without special-case `if` checks.

## Case 3: API Health Check — Timeout ≠ Down

**File:** `examples/health_check.san`

Four microservices each report health: `healthy`, `down`, or `timeout`. The ternary aggregator:
- If any service is `down` → system is `down`
- If all services are `healthy` → system is `healthy`
- If some are `timeout` (none `down`) → system is **maybe** — "partially uncertain"

A binary system (up/down) must classify timeout as down, triggering unnecessary alerts. The ternary system preserves the distinction: timeout is not failure — it's uncertainty.

| Scenario | Ternary | Binary |
|---|---|---|
| All healthy | healthy | up |
| One timeout, rest healthy | maybe | down (false alert) |
| One down | down | down |

The aggregation logic emerges naturally from Kleene operators without custom state machines.

## Case 4: Game NPC Decision — Hesitation Is a Legitimate Behavior

**File:** `examples/npc_decision.san`

An NPC decides between `attack` and `flee` based on distance, threat level, and HP. When no condition is decisive, the ternary NPC returns **maybe** — the player sees hesitation (patrol, look around, random movement). This is a *stable, persistent behavior*, not a transition state.

A binary NPC (same 3 inputs, no extra state variables) has nowhere to put "uncertain." It must guess randomly. The NPC jitters between attack and flee frame-to-frame, which players perceive as buggy behavior.

| Condition met | Ternary | Binary (no extra vars) |
|---|---|---|
| Distance<3 & threat>0.8 | flee | flee |
| HP<0.3 | flee | flee |
| Distance>10 & threat<0.3 | attack | attack |
| None of the above | **maybe** (hesitate) | random (jitter) |

To achieve consistent hesitation in binary, you need at least 1 external state variable (hesitation timer, suspicion counter, etc.). The ternary approach needs zero — `maybe` is a first-class value.

## Summary

| Criterion | Binary | Ternary (Sanyan) |
|---|---|---|
| Values | true, false | true, maybe, false |
| Uncertainty handling | suppress or hack | native propagation |
| Extra state variables | ≥1 for hesitation-like behavior | 0 |
| Data pipeline safety | None/NaN poisoning | maybe stops the chain |
| API health aggregation | up/down forces false alerts | timeout/down distinction |
| Truth tables | 2^n entries | 3^n entries (all correct) |

Three states are the minimum viable model for expressing uncertainty. Sanyan makes `maybe` a first-class citizen — not a library, not a convention, but a language primitive that propagates correctly through every operator.
