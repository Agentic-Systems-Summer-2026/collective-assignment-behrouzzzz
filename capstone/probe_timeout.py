"""
How long does a REAL evaluator request actually need on this proxy?

evaluator.py currently allows 10s. A one-word probe to the same model came
back in 2.2s, but the evaluator's prompt is a few hundred tokens and asks for
a judgement, and the same proxy took 62.6s before giving up on another model.
If 10s is too tight, the aborted requests may themselves be what pushes the
deployment into LiteLLM's cooldown, which then answers 503 -- meaning the
timeout would be causing the outage rather than suffering from it.

This sends the actual evaluator prompt at increasing timeouts and reports
what each one does. Run it a couple of times, a minute apart.

    python3 probe_timeout.py
"""
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, DEFAULT_MODEL

MODEL = os.environ.get("EVALUATOR_MODEL", "Gemma4-31B")
TIMEOUTS = [10, 20, 30, 45, 60, 90]

# The real thing: same shape and size as evaluator.py's two-check prompt.
PROMPT = (
    "You are a strict fact-checking judge for a literature-review assistant.\n"
    "Original user question: According to Liu et al. (2026), overall, how much more "
    "token usage and response time did the agent systems require compared to baseline LLMs?\n"
    "Proposed claim (one piece of a possibly multi-part answer): According to Liu et al. "
    "(2026), agent systems required more than 10 times the token usage and more than twice "
    "the latency of baseline LLMs.\n"
    'Supporting quote (from source "Liu2026"): "Multimodal accuracy remained low (15.5% on '
    "multimodal HLE, 29.2% on AgentClinic NEJM), while resource demands increased "
    'substantially, with >10x token usage and >2x latency."\n\n'
    "Check BOTH of the following:\n"
    "1. Does the quote genuinely and directly support the claim (not a paraphrase or "
    "loose association)?\n"
    "2. Is the claim actually responsive to the ORIGINAL question -- the same topic, "
    "the same metric, the same thing being asked about? A claim about a different "
    "metric or a different aspect is NOT responsive, even if it is a real, "
    "verbatim, well-supported fact from the source.\n"
    "Reply ACCEPT only if BOTH checks pass. Reply with exactly one line:\n"
    "ACCEPT\nor\nREJECT: <short reason, and say which of the two checks failed>"
)

print(f"generator : {DEFAULT_MODEL!r}")
print(f"evaluator : {MODEL!r}")
print(f"prompt    : {len(PROMPT)} chars\n")

first_ok = None
for t in TIMEOUTS:
    t0 = time.time()
    try:
        reply = chat(messages=[{"role": "user", "content": PROMPT}],
                     model=MODEL, timeout=t, temperature=0, retries=0)
        dt = time.time() - t0
        print(f"  timeout={t:<3}  OK    in {dt:5.1f}s  -> {reply.strip()[:50]!r}")
        if first_ok is None:
            first_ok = (t, dt)
    except Exception as e:
        dt = time.time() - t0
        msg = str(e)
        kind = ("503 / deployment in cooldown" if "503" in msg
                else "client timeout" if "timed out" in msg.lower()
                else type(e).__name__)
        print(f"  timeout={t:<3}  FAIL  in {dt:5.1f}s  -> {kind}")
    time.sleep(3)  # let any cooldown settle between probes

print()
if first_ok:
    t, dt = first_ok
    print(f"First success at timeout={t} (took {dt:.1f}s).")
    print(f"Set evaluator.py's timeout to roughly {max(30, int(dt * 3))}s "
          f"— comfortably above the observed time, since a shared proxy is "
          f"slower when other students are hitting it.")
else:
    print("Nothing succeeded at any timeout. That points at the deployment itself\n"
          "rather than the timeout — try again in a few minutes, or ask which\n"
          "models are currently provisioned.")
