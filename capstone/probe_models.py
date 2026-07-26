"""
Which models will this proxy actually serve right now?

The evaluator must use a model DIFFERENT from the generator (evaluator.py
enforces this), and on the course sandbox individual model deployments come
and go: GLM 5.2 and Claude Haiku 3 were already recorded as unusable, and
Gemma4-31B and gemma4-small-12B have since started failing too. Guessing the
next name one run at a time is slow, so ask directly with a one-token prompt.

Add any other model names your course offers to CANDIDATES.

    python3 probe_models.py
"""
import os
import time

from common.llm import chat, DEFAULT_MODEL, PROVIDER

CANDIDATES = [
    "Gemma4-31B",
    "gemma4-small-12B",
    "GLM 5.2",
    "Claude Haiku 3",
    # add whatever else the course lists:
    # "Claude Sonnet 4.5", "Llama-4", "Qwen-3", ...
]

print(f"provider        : {PROVIDER}")
print(f"generator model : {DEFAULT_MODEL!r}   <- this one is working")
print(f"EVALUATOR_MODEL : {os.environ.get('EVALUATOR_MODEL', '(unset)')!r}\n")

probe = [{"role": "user", "content": "Reply with the single word: OK"}]
working = []

for name in CANDIDATES:
    if name.strip().lower() == DEFAULT_MODEL.strip().lower():
        print(f"  SKIP     {name}  (same as generator; evaluator.py rejects this)")
        continue
    t0 = time.time()
    try:
        reply = chat(probe, model=name)
        dt = time.time() - t0
        print(f"  OK       {name}  ({dt:.1f}s)  -> {str(reply)[:40]!r}")
        working.append(name)
    except Exception as e:
        dt = time.time() - t0
        msg = str(e)
        kind = ("503 / no healthy deployment" if "503" in msg
                else "timeout" if "timed out" in msg.lower()
                else type(e).__name__)
        print(f"  FAIL     {name}  ({dt:.1f}s)  -> {kind}")

print()
if working:
    print(f"Usable evaluator models: {', '.join(working)}")
    print(f"\n    export EVALUATOR_MODEL='{working[0]}'")
else:
    print("None of the candidates responded. Either the proxy is genuinely down,\n"
          "or none of these names is provisioned — check the course's model list.\n"
          "The generator still works, so the proxy itself is reachable.")
