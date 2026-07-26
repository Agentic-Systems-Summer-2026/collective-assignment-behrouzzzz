"""
Why are the evaluator's replies coming back empty or cut off mid-sentence?

A real run got None once, then "REJECT: The claim specifies the" -- truncated.
evaluator.py treats anything starting with REJECT as a real content judgement,
so a truncated reply becomes a rejection, spends the rejection budget, and
trips the "already rejected for a content reason" guard. An infrastructure
hiccup ends up looking like a verdict.

Two very different causes need telling apart before fixing anything:
  systematic  -- max_tokens defaults too low, so every longer reply is cut
  intermittent -- the model returns partial output under load

This sends the real evaluator prompt several times and reports what comes back.

    python3 probe_truncation.py
"""
import inspect
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import common.llm as llm
from common.llm import chat, DEFAULT_MODEL

MODEL = os.environ.get("EVALUATOR_MODEL", "Gemma4-31B")
RUNS = 6

# A claim the evaluator should REJECT with a full sentence of reasoning -- the
# long-answer path, which is where truncation would show up.
PROMPT = (
    "You are a strict fact-checking judge for a literature-review assistant.\n"
    "Original user question: What dollar cost did any of these five papers report "
    "for running their agent systems?\n"
    "Proposed claim (one piece of a possibly multi-part answer): Deploying LLM-based "
    "agents is limited by increased inference depth and cumulative token cost.\n"
    'Supporting quote (from source "Du2026"): "Although advanced reasoning models can '
    "enhance decision quality, their integration typically increases inference depth "
    "and cumulative token cost, limiting the practicality of deploying LLM-based "
    'agents in demanding operational environments."\n\n'
    "Check BOTH of the following:\n"
    "1. Does the quote genuinely and directly support the claim?\n"
    "2. Is the claim actually responsive to the ORIGINAL question -- the same topic, "
    "the same metric, the same thing being asked about?\n"
    "Reply ACCEPT only if BOTH checks pass. Reply with exactly one line:\n"
    "ACCEPT\nor\nREJECT: <short reason, and say which of the two checks failed>"
)

print(f"generator : {DEFAULT_MODEL!r}")
print(f"evaluator : {MODEL!r}\n")

print("--- what does chat() default to? ---")
try:
    sig = inspect.signature(chat)
    for name, p in sig.parameters.items():
        if p.default is not inspect.Parameter.empty:
            print(f"  {name} = {p.default!r}")
        else:
            print(f"  {name} (required)")
except (TypeError, ValueError) as e:
    print(f"  could not read signature: {e}")

for attr in ("MAX_TOKENS", "DEFAULT_MAX_TOKENS", "MAX_OUTPUT_TOKENS"):
    if hasattr(llm, attr):
        print(f"  llm.{attr} = {getattr(llm, attr)!r}")

accepts_max_tokens = "max_tokens" in inspect.signature(chat).parameters
print(f"\n  chat() accepts max_tokens: {accepts_max_tokens}\n")

print(f"--- {RUNS} identical calls, default settings ---")
lengths = []
for i in range(RUNS):
    t0 = time.time()
    try:
        r = chat(messages=[{"role": "user", "content": PROMPT}],
                 model=MODEL, timeout=45, temperature=0, retries=0)
        dt = time.time() - t0
        if not isinstance(r, str) or not r.strip():
            print(f"  {i+1}. EMPTY   ({dt:4.1f}s)  -> {r!r}")
            lengths.append(0)
            continue
        txt = r.strip()
        lengths.append(len(txt))
        complete = txt.endswith((".", "!", ")")) or txt.upper() == "ACCEPT"
        flag = "looks complete" if complete else "LOOKS TRUNCATED"
        print(f"  {i+1}. {len(txt):>4} chars ({dt:4.1f}s)  {flag}")
        print(f"       {txt[:120]!r}")
    except Exception as e:
        print(f"  {i+1}. ERROR   -> {type(e).__name__}: {str(e)[:70]}")
    time.sleep(2)

if accepts_max_tokens:
    print("\n--- same call with max_tokens=200 explicitly ---")
    for i in range(3):
        try:
            r = chat(messages=[{"role": "user", "content": PROMPT}], model=MODEL,
                     timeout=45, temperature=0, retries=0, max_tokens=200)
            txt = (r or "").strip()
            complete = txt.endswith((".", "!", ")")) or txt.upper() == "ACCEPT"
            print(f"  {i+1}. {len(txt):>4} chars  "
                  f"{'looks complete' if complete else 'LOOKS TRUNCATED'}")
            print(f"       {txt[:120]!r}")
        except Exception as e:
            print(f"  {i+1}. ERROR -> {type(e).__name__}: {str(e)[:70]}")
        time.sleep(2)

print("\n--- reading ---")
if lengths and len(set(lengths)) == 1 and lengths[0] > 0:
    print(f"  Every reply was exactly {lengths[0]} chars. An identical ceiling every\n"
          f"  time means a token limit, not load. Fix it at the source by passing\n"
          f"  max_tokens explicitly in evaluator.py.")
elif lengths and max(lengths) - min(lengths) > 40:
    print("  Lengths vary a lot, and some replies are empty or cut short. That points\n"
          "  at the model/proxy under load rather than a fixed limit, so evaluator.py\n"
          "  needs to RECOGNISE a truncated reply and treat it as a technical error\n"
          "  instead of a rejection.")
else:
    print("  Nothing conclusive -- run it again while the proxy is busy.")