"""
Reproduces the evaluator outage seen in a real run and checks the response.

Observed before the fix: the model found a correct, quote-verified claim, the
evaluator returned 503, and the run then spent four turns resubmitting into a
dead service before reporting "INSUFFICIENT CONTEXT (turn limit reached)".
That report is wrong -- the sources DID contain the answer -- and in the logs
it is indistinguishable from a genuine absence.

Run from the capstone directory:  python3 test_evaluator_outage.py
"""
import json
import sys
import types

import tools

# Stub the model: it lists sources, searches once, then submits a real claim
# and keeps resubmitting it, which is what the live model did.
QUOTE = ("Overall, these results highlight that the agent-based systems significantly "
         "elevate computational demands, consistently requiring more than tenfold the "
         "token usage and at least twice the response time compared to baseline LLMs.")
FINISH = json.dumps({"tool": "finish", "claims": [{
    "source_id": "Liu2026", "quote": QUOTE,
    "statement": "Agent systems required over tenfold the tokens and twice the time."}]})

calls = {"n": 0, "evals": 0}


def fake_chat(msgs, cache=False):
    calls["n"] += 1
    if calls["n"] == 1:
        return json.dumps({"tool": "list_sources"})
    return FINISH


def fake_evaluate(question, quote, source_id, original_question=None):
    calls["evals"] += 1
    return {"ok": False, "technical_error": True,
            "reason": "Evaluator technical failure: Sandbox unreachable: HTTP Error 503"}


import common.llm as llm
llm.chat = fake_chat
import evaluator
evaluator.evaluate = fake_evaluate

import agent
agent.chat = fake_chat
agent.evaluate = fake_evaluate

print("\nSimulating an evaluator that is down for the whole run...\n")
answer = agent.answer_question(
    "According to Liu et al. (2026), how much more token usage did agents require?",
    verbose=False)

fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if detail:
        print(f"          {detail}")
    if not cond:
        fails.append(name)


check("the quote itself really does verify (so this is not a content problem)",
      tools.verify_quote("Liu2026", QUOTE).get("ok") is True)
check("answer does NOT claim the sources lack an answer",
      "INSUFFICIENT CONTEXT" not in answer, f"answer: {answer[:90]}")
check("answer names the real cause", "EVALUATOR UNAVAILABLE" in answer,
      f"answer: {answer[:90]}")
check("run stopped early instead of grinding to the turn limit",
      calls["n"] <= 6, f"{calls['n']} model calls used")
check("evaluator was not hammered indefinitely",
      calls["evals"] <= 12, f"{calls['evals']} evaluator calls")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILURES'}\n")
sys.exit(1 if fails else 0)
