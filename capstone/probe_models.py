"""
Which models will this proxy actually serve right now?

The evaluator must use a model DIFFERENT from the generator (evaluator.py
enforces this). On the course sandbox, individual model deployments come and
go -- Claude Haiku 3 is confirmed dead; Gemma4-31B and GLM 5.2 both work but
were previously misdiagnosed as broken when the real problem was too short a
client-side timeout (see probe_timeout.py). This script does not assume any
one of them is best -- it only reports which candidates respond and how
fast, so the choice of EVALUATOR_MODEL is made from evidence, not guesswork.

Add or remove names in CANDIDATES to match what your course actually offers.

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
    "Amazon-Nova-Lite",
    "glm-4.7",
    "GPT OSS",
    "Kimi K2.7 Code",
    "Minimax M2.7",
    "olmo",
    "Qwen3 32B",
    "Qwen3.5 397B",
    "Qwen3.6-27B (small)",
]

print(f"provider        : {PROVIDER}")
print(f"generator model : {DEFAULT_MODEL!r}   <- this one is working")
print(f"EVALUATOR_MODEL : {os.environ.get('EVALUATOR_MODEL', '(unset)')!r}\n")

probe = [{"role": "user", "content": "Reply with the single word: OK"}]
working = []  # (name, latency_seconds)

for name in CANDIDATES:
    if name.strip().lower() == DEFAULT_MODEL.strip().lower():
        print(f"  SKIP     {name}  (same as generator; evaluator.py rejects this)")
        continue
    t0 = time.time()
    try:
        reply = chat(probe, model=name)
        dt = time.time() - t0
        print(f"  OK       {name}  ({dt:.1f}s)  -> {str(reply)[:40]!r}")
        working.append((name, dt))
    except Exception as e:
        dt = time.time() - t0
        msg = str(e)
        kind = ("503 / no healthy deployment" if "503" in msg
                else "timeout" if "timed out" in msg.lower()
                else type(e).__name__)
        print(f"  FAIL     {name}  ({dt:.1f}s)  -> {kind}")

print()
if working:
    working.sort(key=lambda pair: pair[1])  # fastest first, on THIS probe only
    print("Responded, ranked by this probe's latency (fastest first):")
    for name, dt in working:
        print(f"    {dt:5.1f}s  {name}")
    print(
        f"\n  This is a one-word round trip, not the evaluator's real prompt "
        f"(~1200 chars asking for a judgement) -- probe_timeout.py showed a "
        f"real evaluator call can run 15-66s even on a model that answers "
        f"'OK' in under 2s, because the workload is different, not just "
        f"longer. Do not export a model straight from this list.\n\n"
        f"  Next: run probe_timeout.py against the top 2-3 candidates above "
        f"(edit its MODEL line, or pass EVALUATOR_MODEL per run) to see real "
        f"evaluator-call latency before choosing. Only then:\n\n"
        f"    export EVALUATOR_MODEL='<the one that held up under probe_timeout.py>'"
    )
else:
    print("None of the candidates responded. Either the proxy is genuinely down,\n"
          "or none of these names is provisioned — check the course's model list.\n"
          "The generator still works, so the proxy itself is reachable.")
