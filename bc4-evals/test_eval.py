"""CI regression gate (runs on every push via .github/workflows/eval.yml).

Small LIVE sweep against the course endpoint -- OU LiteLLM Sandbox if
LITELLM_API_KEY is set, else OpenRouter via OPENROUTER_API_KEY -- covering the
first EVAL_LIVE_N cases (default 5), temperature 0, response caching on. Keep
it capped -- a push should cost pennies. The gate fails the build when the
pass rate drops below harness.PASS_THRESHOLD: that's the point. When you
improve your system, thresholds only move UP, with evidence.
"""
import os
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# The workflow yml exports BOTH secrets and lets either one satisfy the gate
# (OU LiteLLM Sandbox is our primary endpoint; OpenRouter is the fallback).
# The starter only checked OPENROUTER_API_KEY, which would silently skip this
# test on OU-sandbox-only credentials even though the workflow file itself
# already runs pytest in that case.
if not (os.environ.get("LITELLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")):
    pytest.skip("Neither LITELLM_API_KEY nor OPENROUTER_API_KEY is set -- eval gate "
                "needs one repository secret (Settings -> Secrets and variables -> "
                "Actions).", allow_module_level=True)

import harness  # noqa: E402

LIVE_N = int(os.environ.get("EVAL_LIVE_N", "5"))


def test_regression_gate():
    results = harness.run_sweep(limit=LIVE_N)
    rate = sum(r["pass"] for r in results) / len(results)
    failing = [f"{r['id']}: {r['assertion']} / {r['judge']}"
               for r in results if not r["pass"]]
    assert rate >= harness.PASS_THRESHOLD, (
        f"pass rate {rate:.0%} < threshold {harness.PASS_THRESHOLD:.0%}\n"
        + "\n".join(failing))