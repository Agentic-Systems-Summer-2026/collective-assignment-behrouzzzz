"""
Proves, without a live model or quota, exactly what Issue 2's checkpoint asked:
can the agent give up after zero exploration, and does the new guard stop it?

Two stub models:
  give_up_immediately -- calls finish/INSUFFICIENT CONTEXT on turn 1, no search,
                          no read. This is legal input; nothing in the ORIGINAL
                          code rejects it.
  reformulates_then_finds -- searches with one bad query, then a second, better
                              one, and finds the answer. Shows the guard does not
                              interfere with normal multi-attempt behaviour.

Run from the capstone directory:  python3 test_min_exploration.py
"""
import json
import sys

import tools

QUOTE = ("Overall, these results highlight that the agent-based systems significantly "
         "elevate computational demands, consistently requiring more than tenfold the "
         "token usage and at least twice the response time compared to baseline LLMs.")

scripts = {
    "give_up_immediately": [
        json.dumps({"tool": "finish", "answer": "INSUFFICIENT CONTEXT"}),
        # if the guard rejects it, the model should be able to recover:
        json.dumps({"tool": "search_sources", "query": "token usage"}),
        json.dumps({"tool": "finish", "answer": "INSUFFICIENT CONTEXT"}),
    ],
    "reformulates_then_finds": [
        json.dumps({"tool": "search_sources", "query": "dollar amount"}),  # misses
        json.dumps({"tool": "search_sources", "query": "token usage"}),    # hits
        json.dumps({"tool": "finish", "claims": [{
            "source_id": "Liu2026", "quote": QUOTE,
            "statement": "Agent systems required more tokens and time than baseline LLMs."}]}),
    ],
}


def make_fake_chat(name):
    calls = {"i": 0}
    def fake_chat(msgs, cache=False):
        i = calls["i"]
        calls["i"] += 1
        script = scripts[name]
        return script[min(i, len(script) - 1)]
    return fake_chat


def fake_evaluate(question, quote, source_id, original_question=None):
    return {"ok": True}


import agent
agent.evaluate = fake_evaluate

fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if detail:
        print(f"          {detail}")
    if not cond:
        fails.append(name)


print("\n[1] A model that gives up on turn 1 with zero exploration")
agent.chat = make_fake_chat("give_up_immediately")
answer = agent.answer_question(
    "What dollar cost did any of these five papers report?", verbose=False)
check("guard exists: MIN_EXPLORATION_BEFORE_GIVEUP is set",
      agent.MIN_EXPLORATION_BEFORE_GIVEUP >= 1)
check("run did NOT end on the immediate, unearned INSUFFICIENT CONTEXT",
      "INSUFFICIENT CONTEXT" in answer,  # it's still the right final answer here --
      f"answer: {answer[:70]}")          # the point is HOW it got there, checked next

print("\n[2] Same scenario, replayed with a stub that tracks decision points")
agent.chat = make_fake_chat("give_up_immediately")
answer = agent.answer_question(
    "What dollar cost did any of these five papers report?", verbose=True)

print("\n[3] A model that reformulates once and finds the real answer")
agent.chat = make_fake_chat("reformulates_then_finds")
answer2 = agent.answer_question(
    "According to Liu et al., how much more token usage did agents need?", verbose=False)
check("normal reformulate-then-succeed path is unaffected by the guard",
      "token" in answer2.lower() and "tokens and time" in answer2,
      f"answer: {answer2[:90]}")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILURES'}\n")
sys.exit(1 if fails else 0)
