"""
Does Case 12's rejection pattern change with a different evaluator model?

Case 12 asks a RELATIONSHIP question ("how does split A relate to split B?")
that can only be answered by combining one claim from each of two sources.
In the live run on 2026-08-06, gemma4-small-12B (the project's current
evaluator) rejected every single-source claim with Check 2 ("not responsive
to the original question") because each claim, alone, only defines one side
of the relationship rather than stating the relationship itself. Only one
of four attempted claims (a Du2026 one) was ever accepted.

This probe does NOT change evaluator.py or agent.py. It calls
evaluator.evaluate() directly -- the same function agent.py calls -- against
the exact three claims that were rejected in the real Case 12 log
(logs/20260806T232658_65cc2b32a1_e89eaf.json), so the only variable is which
model is doing the judging. Each (model, claim) pair is run 3 times, because
evaluator judgments are not guaranteed deterministic even at temperature=0
on a shared proxy, and a single run cannot distinguish "this model judges
this differently" from "this run happened to land differently."

Candidates, and why each is here (see Conversation history / probe_models.py
2026-08-06 for the full latency table):
  - gemma4-small-12B  current evaluator, included as the baseline to compare against
  - GLM 5.2           previously rejected for reliability (3/6 AttributeError in an
                       earlier probe), but 6/6 clean on 2026-08-06's probe_timeout.py
                       run -- worth re-testing on real judgment content, not just
                       reachability
  - GPT OSS           different family from both the generator (Qwen3 Coder 30B)
                       and gemma4-small-12B; fast (~1.0s one-word probe)
  - Minimax M2.7       different family, fast enough (~2.0s one-word probe),
                       previously untested on this project's actual judgment task

Deliberately excluded (per project owner, 2026-08-06):
  - Qwen3 32B / Qwen3.5 397B / Qwen3.6-27B -- same family as the generator
    (Qwen3 Coder 30B); would reintroduce the correlated-error risk cross-model
    evaluation exists to prevent, regardless of how well it scores here.
  - Amazon-Nova-Lite -- "Lite" naming suggests a lightweight model; unlikely
    to help with a nuanced relationship-judgment task, and not worth the
    quota to confirm that.
  - Kimi K2.7 Code -- 62s per one-word probe. Even if its reasoning were
    better, this is impractical for an evaluator that runs on every claim.

Run from inside capstone/ (same place as probe_timeout.py):

    python3 probe_evaluator_reasoning.py

Reads no environment variable for the model -- it sets EVALUATOR_MODEL
itself, once per candidate, immediately before each call.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluator import evaluate  # noqa: E402
from common.llm import DEFAULT_MODEL as GENERATOR_MODEL  # noqa: E402

CANDIDATES = [
    "gemma4-small-12B",
    "GLM 5.2",
    "GPT OSS",
    "Minimax M2.7",
]

REPEATS_PER_CLAIM = 3

ORIGINAL_QUESTION = (
    "How does the symbolic-vs-neural paradigm split (Abou Ali et al.) relate "
    "to the parameter-driven-vs-parameter-free split (Du et al.) as two "
    "different ways of categorizing LLM agent approaches?"
)

# The exact three claims Case 12's live run rejected on 2026-08-06, pulled
# verbatim from logs/20260806T232658_65cc2b32a1_e89eaf.json. A fourth claim
# (Du2026 / parameter-free optimization) was accepted in that run and is not
# included here, since the question is specifically why these three failed.
REJECTED_CLAIMS = [
    {
        "label": "AbouAli2025 / dual-paradigm framework (rejected, attempt 1)",
        "source_id": "AbouAli2025",
        "quote": (
            "This survey cuts through this confusion by introducing a novel "
            "dual-paradigm framework that categorizes agentic systems into "
            "two distinct lineages: the symbolic/classical (relying on "
            "algorithmic planning and persistent state) and the "
            "neural/generative (leveraging stochastic generation and "
            "prompt-driven orchestration)."
        ),
        "statement": (
            "The symbolic-vs-neural paradigm split, as introduced by Abou "
            "Ali et al., categorizes agentic systems into two lineages: "
            "symbolic/classical systems that rely on algorithmic planning "
            "and persistent state, versus neural/generative systems that "
            "leverage stochastic generation and prompt-driven orchestration."
        ),
        "original_rejection_reason": (
            "The claim is not responsive to the original question (Check 2 "
            "failed). The question asks for a comparison/relationship "
            "between two specific frameworks, but the claim only defines "
            "one of them."
        ),
    },
    {
        "label": "Du2026 / parameter-driven vs parameter-free (rejected, attempt 1)",
        "source_id": "Du2026",
        "quote": (
            "In this survey, we provide a comprehensive review of LLM-based "
            "agent optimization approaches, categorizing them into "
            "parameter-driven and parameter-free methods."
        ),
        "statement": (
            "The parameter-driven-vs-parameter-free split, as categorized "
            "by Du et al., classifies LLM-based agent optimization "
            "approaches into two categories: parameter-driven methods that "
            "modify model parameters, and parameter-free methods that "
            "optimize behavior without changing parameters."
        ),
        "original_rejection_reason": (
            "The claim is not fully responsive to the original question as "
            "it only defines one side of the requested comparison (Du et "
            "al.) without addressing the relationship to the "
            "symbolic-vs-neural split (Abou Ali et al.). Check 2 failed."
        ),
    },
    {
        "label": "AbouAli2025 / neural paradigm break from symbolic (rejected, attempt 2)",
        "source_id": "AbouAli2025",
        "quote": (
            "This shift marks the definitive break from the symbolic "
            "tradition. Agency in the neural paradigm is an emergent "
            "property of prompt-driven orchestration, not a product of "
            "internal symbolic logic."
        ),
        "statement": (
            "The neural paradigm, as defined by Abou Ali et al., differs "
            "from the symbolic paradigm in that agency emerges from "
            "prompt-driven orchestration rather than internal symbolic "
            "logic."
        ),
        "original_rejection_reason": "The claim is not responsive to the original question (Check 2 failed).",
    },
]

print(f"generator model : {GENERATOR_MODEL!r}")
print(f"candidates      : {', '.join(CANDIDATES)}")
print(f"repeats/claim   : {REPEATS_PER_CLAIM}\n")

results = {}  # model -> claim label -> list of "ACCEPT" / "REJECT: ..." / "ERROR: ..."

for model in CANDIDATES:
    if model.strip().lower() == GENERATOR_MODEL.strip().lower():
        print(f"SKIP {model} -- same as generator, evaluator.py would reject this")
        continue
    os.environ["EVALUATOR_MODEL"] = model
    results[model] = {}
    print(f"===== {model} =====")
    for claim in REJECTED_CLAIMS:
        outcomes = []
        for i in range(1, REPEATS_PER_CLAIM + 1):
            t0 = time.time()
            try:
                verdict = evaluate(
                    question=claim["statement"],
                    quote=claim["quote"],
                    source_id=claim["source_id"],
                    original_question=ORIGINAL_QUESTION,
                )
                dt = time.time() - t0
                if verdict.get("ok"):
                    tag = "ACCEPT"
                elif verdict.get("technical_error"):
                    tag = f"TECH-ERROR: {verdict.get('reason', '')[:60]}"
                else:
                    tag = f"REJECT: {verdict.get('reason', '')[:60]}"
                print(f"  [{claim['label'][:55]:55}] run {i}: {tag}  ({dt:.1f}s)")
                outcomes.append(tag)
            except Exception as e:
                dt = time.time() - t0
                print(f"  [{claim['label'][:55]:55}] run {i}: EXCEPTION {e!r}  ({dt:.1f}s)")
                outcomes.append(f"EXCEPTION: {e}")
            time.sleep(2)
        results[model][claim["label"]] = outcomes
    print()

print("######################################################################")
print("# SUMMARY -- paste everything from here up, plus the full output above")
print("######################################################################")
for model, per_claim in results.items():
    print(f"\n{model}:")
    for label, outcomes in per_claim.items():
        accept_count = sum(1 for o in outcomes if o == "ACCEPT")
        print(f"  {label[:60]:60} {accept_count}/{len(outcomes)} ACCEPT  -> {outcomes}")

print(
    "\nRead this alongside the original Case 12 log "
    "(logs/20260806T232658_65cc2b32a1_e89eaf.json). If a candidate accepts "
    "single-source claims that gemma4-small-12B consistently rejects, that is "
    "evidence the rejection is a model-specific interpretation difference, not "
    "an inherent limit of the two-check design. If every candidate rejects "
    "these the same way, that points at the claim-level design itself -- a "
    "relationship question may need a composite-claim mechanism the current "
    "architecture doesn't have, regardless of which model judges it."
)
