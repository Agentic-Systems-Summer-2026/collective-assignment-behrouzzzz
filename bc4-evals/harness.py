#!/usr/bin/env python3
"""Build Challenge 4 starter — evaluation harness.

Run the full local sweep from the repo root:
    python3 bc4-evals/harness.py            # all cases, cached
CI runs the pytest wrapper (test_eval.py) on every push: a small live sweep
capped by EVAL_LIVE_N (default 5).

The harness evaluates TARGET below. It defaults to a plain model call — point
it at YOUR system (bc1 agent, capstone slice) by replacing `target()`.

Three layers, per the pre-read:
  1. assertions  — cheap, deterministic checks (see check_case)
  2. LLM-as-judge — calibrate against your own labels before trusting it
  3. error analysis — look at the failures, not just the score
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[0]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "capstone"))

from common.llm import chat, STATS  # noqa: E402
import agent as capstone_agent  # noqa: E402

CASES = HERE / "cases.jsonl"

PASS_THRESHOLD = 0.8  # the CI gate fails below this — tune with evidence


def target(prompt: str) -> str:
    """The system under test: the capstone Literature Review Assistant.

    Each case's "prompt" is a real user question. answer_question() runs the
    full tool loop (search/read/verify/finish) against the 5-paper corpus and
    the OU LiteLLM Sandbox, and returns the final answer string -- the same
    thing a person using the assistant would see.
    """
    return capstone_agent.answer_question(prompt, verbose=False)


def check_case(case: dict, output: str) -> tuple[bool, str]:
    """Layer 1: assertions. Deterministic, explainable, fast."""
    out = output.lower()
    for s in case.get("must_contain", []):
        if s.lower() not in out:
            return False, f"missing required substring: {s!r}"
    for s in case.get("must_not_contain", []):
        if s.lower() in out:
            return False, f"contains forbidden substring: {s!r}"
    if "max_chars" in case and len(output) > case["max_chars"]:
        return False, f"too long: {len(output)} > {case['max_chars']}"
    return True, "ok"


def judge_case(case: dict, output: str) -> tuple[bool, str]:
    """Layer 2: LLM-as-judge, for qualities assertions can't express.
    Calibrate: run it on a handful of outputs you've labeled yourself and
    report agreement in your write-up before you trust it in the gate."""
    if "judge_criteria" not in case:
        return True, "no judge criteria"
    verdict = chat([{"role": "user", "content":
                     f"You are a strict grader. Criteria: {case['judge_criteria']}\n\n"
                     f"CANDIDATE ANSWER:\n{output}\n\n"
                     'Reply ONLY with JSON {"pass": true|false, "reason": "<one line>"}'}],
                   max_tokens=120, cache=True)
    try:
        j = json.loads(verdict[verdict.find("{"):verdict.rfind("}") + 1])
        return bool(j.get("pass")), j.get("reason", "")
    except Exception:
        return False, "judge reply unparseable: " + verdict[:80]


def run_sweep(limit=None):
    import time
    cases = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    if limit:
        cases = cases[:limit]
    results = []
    print(f"running {len(cases)} case(s) against the live agent -- each one is a "
          f"full tool loop, so this can take anywhere from seconds to a couple of "
          f"minutes PER case; progress prints as each one finishes.\n", flush=True)
    for i, c in enumerate(cases, 1):
        t0 = time.time()
        print(f"[{i}/{len(cases)}] {c['id']} ...", end=" ", flush=True)
        out = target(c["prompt"])
        ok_a, why_a = check_case(c, out)
        ok_j, why_j = judge_case(c, out) if ok_a else (False, "skipped (assertion failed)")
        dt = time.time() - t0
        result = {"id": c["id"], "pass": ok_a and ok_j,
                  "assertion": why_a, "judge": why_j, "output": out}
        results.append(result)
        note = why_a if why_a != "ok" else why_j
        print(f"{'PASS' if result['pass'] else 'FAIL'} ({dt:.0f}s) {note}", flush=True)
        # Write after every case, not just at the end -- if this needs to be
        # interrupted (or the sandbox stalls on a later case), everything up
        # to that point is already on disk instead of lost.
        (HERE / "last_run.json").write_text(json.dumps(results, indent=1))
    return results


def main():
    results = run_sweep()
    rate = sum(r["pass"] for r in results) / len(results)
    print(f"{'ID':10} {'PASS':5} notes")
    for r in results:
        note = r["assertion"] if r["assertion"] != "ok" else r["judge"]
        print(f"{r['id']:10} {str(r['pass']):5} {note}")
    print(f"\npass rate: {rate:.0%}  (threshold {PASS_THRESHOLD:.0%})   STATS: {STATS}")
    # Layer 3 starts here: open the failing outputs and READ them.
    (HERE / "last_run.json").write_text(json.dumps(results, indent=1))
    print("full outputs -> bc4-evals/last_run.json (do your error analysis there)")


if __name__ == "__main__":
    main()