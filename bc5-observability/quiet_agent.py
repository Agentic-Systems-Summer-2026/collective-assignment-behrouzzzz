#!/usr/bin/env python3
"""Build Challenge 5 — instrumented agent

Normal run:
    python3 bc5-observability/quiet_agent.py

Incident run (forces a bad model name on the "answers" step, matching the known-broken entries in prob-models.txt, e.g. "Claude Haiku 33"): BC5_BREAK_MODEL="Claude Haiku 33" python3 bc5-observability/quiet_agent.py

Every pipeline event (step start, step end, human decision, summary write, session end) is appended as one JSON line to trace.jsonl, flushed to disk immediately.
"""
import datetime
import json
import os
import pathlib
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, STATS, DEFAULT_MODEL, BASE, PROVIDER, _key

HERE = pathlib.Path(__file__).resolve().parent
TOPIC = "why long-running agents need checkpoints"

TRACE_PATH = HERE / "trace.jsonl"
RECORDS_PATH = HERE / "bc5-records.md"
GATEWAY_LOG = pathlib.Path.home() / ".openclaw" / "gateway.log"

SESSION_ID = uuid.uuid4().hex[:12]
PID = os.getpid()
_SESSION_START = time.time()
_SESSION_ENTRIES = []      # every trace entry logged by this run, in order
_last_step = None          # last step attempted, for the generic crash handler


def _log(step, model, prompt, response, latency_s, decision, phase="end", **extra):
    """Append one structured JSONL line and flush it to disk immediately."""
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "session_id": SESSION_ID,
        "pid": PID,
        "elapsed_s": round(time.time() - _SESSION_START, 3),
        "step": step,
        "phase": phase,
        "model": model,
        "prompt_chars": len(prompt) if prompt else 0,
        "response_chars": len(response) if response else 0,
        "latency_s": round(latency_s, 3),
        "decision": decision,
        "stats_calls_total": STATS["calls"],
        "stats_tokens_total": STATS["tokens"],
    }
    entry.update(extra)
    _SESSION_ENTRIES.append(entry)
    with TRACE_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())   # crash-safe: entry is on disk before we continue
    return entry


def traced_chat(step, messages, model=None):
    """Call chat(), logging a start event, then a success/failure end event."""
    global _last_step
    _last_step = step
    use_model = model or DEFAULT_MODEL
    prompt_text = messages[-1]["content"] if messages else ""

    _log(step, use_model, prompt_text, "", 0.0, "started", phase="start")

    calls_before, tokens_before = STATS["calls"], STATS["tokens"]
    t0 = time.time()
    try:
        response = chat(messages, model=model) if model else chat(messages)
        latency = time.time() - t0
        _log(step, use_model, prompt_text, response, latency, "success", phase="end",
             tokens_delta=STATS["tokens"] - tokens_before,
             calls_delta=STATS["calls"] - calls_before)
        return response
    except Exception as e:
        latency = time.time() - t0
        _log(step, use_model, prompt_text, "", latency, "failed", phase="end",
             tokens_delta=STATS["tokens"] - tokens_before,
             calls_delta=STATS["calls"] - calls_before,
             error_type=type(e).__name__, error=str(e),
             traceback=traceback.format_exc())
        raise


# ---------------------------------------------------------------- cost -----

def _scan_gateway_log():
    """Best-effort scan of ~/.openclaw/gateway.log for usage/token info.
    Returns (found, calls_seen, tokens_seen, matched_lines)."""
    if not GATEWAY_LOG.exists():
        return False, None, None, []
    try:
        lines = GATEWAY_LOG.read_text(errors="replace").splitlines()
    except Exception as e:
        return False, None, None, [f"<could not read gateway.log: {e}>"]

    usage_lines = [ln for ln in lines if re.search(r"token|usage|completion", ln, re.I)]
    if not usage_lines:
        return False, None, None, []

    total_tokens, found_tokens = 0, False
    for ln in usage_lines:
        m = re.search(r"tokens?[\"':=\s]+(\d+)", ln, re.I)
        if m:
            total_tokens += int(m.group(1))
            found_tokens = True
    return True, len(usage_lines), (total_tokens if found_tokens else None), usage_lines[-20:]


def _fetch_model_catalog():
    """One-shot GET to {BASE}/v1/models — the OU LiteLLM Sandbox's own
    suggestion when it rejects a bad model name ("Call /v1/models to view
    available models for your key"). Reuses BASE/_key from common.llm; no
    new dependencies. Tells us whether the provider exposes per-token
    pricing anywhere, which is the one usage-adjacent mechanism in this
    environment we hadn't checked yet."""
    try:
        req = urllib.request.Request(BASE + "/v1/models",
                                      headers={"Authorization": "Bearer " + _key()})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        return True, data, None
    except Exception as e:
        return False, None, str(e)


def append_cost_reconciliation():
    """Append an auto-generated cost reconciliation block to bc5-records.md."""
    found, gw_calls, gw_tokens, sample_lines = _scan_gateway_log()
    my_calls, my_tokens = STATS["calls"], STATS["tokens"]
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    lines = [f"\n### Auto cost reconciliation — {ts} UTC (session `{SESSION_ID}`)\n",
             "| Source | Calls | Tokens |", "|---|---|---|",
             f"| trace.jsonl (`STATS` at end of run) | {my_calls} | {my_tokens} |"]

    if found:
        lines.append(f"| ~/.openclaw/gateway.log (heuristic scan) | "
                      f"{gw_calls if gw_calls is not None else '—'} | "
                      f"{gw_tokens if gw_tokens is not None else '—'} |")
        if gw_tokens is not None:
            match = gw_tokens == my_tokens
            lines.append(f"\n**Match:** {'yes' if match else 'no — numbers differ, see raw lines below'}")
        else:
            lines.append("\n**Match:** gateway log has usage-adjacent lines but no parseable "
                          "token count — inspect the raw lines below manually.")
        lines.append("\n_Heuristic scan: matches lines containing 'token', 'usage', or "
                      "'completion' and regex-extracts a number after 'token(s)'. "
                      "Cross-check against the Control UI (http://127.0.0.1:18789) "
                      "before treating this as final._")
        lines.append("\n<details><summary>Matched gateway.log lines (up to 20)</summary>\n\n```")
        lines.extend(sample_lines)
        lines.append("```\n</details>")
    else:
        lines.append("| ~/.openclaw/gateway.log | not available | not available |")
        if GATEWAY_LOG.exists():
            try:
                total_lines = len(GATEWAY_LOG.read_text(errors="replace").splitlines())
            except Exception:
                total_lines = None
            lines.append(f"\n**Match:** cannot be determined automatically — "
                          f"`{GATEWAY_LOG}` has {total_lines if total_lines is not None else 'some'} "
                          "line(s), but none match 'token'/'usage'/'completion'. This log's entries "
                          "are OpenClaw's own WebSocket RPC calls (e.g. `sessions.subscribe`, "
                          "`agents.list`, `chat.history`) for the Control UI itself — not LLM "
                          "completion requests. `common/llm.py`'s `chat()` talks directly to "
                          f"`{BASE}`, which does not pass through this gateway.")
        else:
            lines.append(f"\n**Match:** cannot be determined automatically — "
                          f"`{GATEWAY_LOG}` does not exist on this machine. Check the Control UI "
                          "at http://127.0.0.1:18789 manually and record the numbers there instead.")

    ok, catalog, err = _fetch_model_catalog()
    lines.append(f"\n**Provider model catalog check** (`{PROVIDER}`, `GET {BASE}/v1/models`):")
    if ok:
        models = catalog.get("data", catalog) if isinstance(catalog, dict) else catalog
        dump = json.dumps(models, indent=2)[:2000]
        has_pricing = any(k in dump.lower() for k in ("price", "cost", "per_token", "pricing", "rate"))
        n = len(models) if isinstance(models, list) else "?"
        lines.append(("Pricing-related fields detected — see raw dump below."
                       if has_pricing else
                       f"Reachable, {n} model(s) listed, but no per-token pricing fields found. "
                       "This confirms the sandbox exposes token counts (already captured above "
                       "via `STATS`) as the only usage signal — not a dollar cost figure.")
                      + " Verified live, this run.")
        lines.append("\n<details><summary>Raw /v1/models response (truncated)</summary>\n\n```json")
        lines.append(dump)
        lines.append("```\n</details>")
    else:
        lines.append(f"Not reachable this run: {err}")

    block = "\n".join(lines) + "\n"
    try:
        current = RECORDS_PATH.read_text() if RECORDS_PATH.exists() else ""
        marker = "## PART C — Final Submission Checklist"
        if marker in current:
            head, sep, tail = current.partition(marker)
            RECORDS_PATH.write_text(head + block + "\n" + sep + tail)
        else:
            with RECORDS_PATH.open("a") as f:
                f.write(block)
    except Exception as e:
        print(f"(could not append cost reconciliation to bc5-records.md: {e})")
    return block


# ------------------------------------------------------------------ main ---

def main():
    break_model = os.environ.get("BC5_BREAK_MODEL")

    plan = traced_chat("plan", [{"role": "user", "content":
                        f"List 3 short bullet questions someone should answer to explain: {TOPIC}"}])

    try:
        answers = traced_chat("answers", [{"role": "user", "content":
                               "Answer each question in 2 sentences:\n" + plan}],
                               model=break_model)
    except Exception as e:
        tb = traceback.format_exc()
        _log("pipeline", break_model or DEFAULT_MODEL, "", "", 0.0, "aborted", phase="end",
             error_type=type(e).__name__, error=str(e), traceback=tb)
        print(f"\nPipeline aborted: {e}")
        print("See trace.jsonl — the 'answers' step is where this broke.")
        sys.exit(1)

    summary = traced_chat("summary", [{"role": "user", "content":
                           "Compress this into a 4-sentence summary for a student:\n" + answers}])

    # --- Human-in-the-loop gate: nothing is written without approval ---
    print("\n--- Pending output (summary.md) ---")
    print(summary)
    print(f"\nCost so far: {STATS['calls']} calls, {STATS['tokens']} tokens")
    reply = input("Approve write to summary.md? [y/N]: ").strip().lower()

    summary_path = HERE / "summary.md"
    if reply == "y":
        _log("human_approval", "-", "", "", 0.0, "approved", phase="end")
        _log("summary_write", "-", "", "", 0.0, "started", phase="start",
             file_path=str(summary_path))
        summary_path.write_text(f"# {TOPIC}\n\n{summary}\n")
        _log("summary_write", "-", "", "", 0.0, "written", phase="end",
             file_path=str(summary_path), file_exists=summary_path.exists(),
             file_size_bytes=summary_path.stat().st_size if summary_path.exists() else 0)
        print("Approved. summary.md written.")
    else:
        _log("human_approval", "-", "", "", 0.0, "rejected", phase="end")
        _log("summary_write", "-", "", "", 0.0, "not_written", phase="end",
             file_path=str(summary_path), file_exists=summary_path.exists(),
             file_size_bytes=(summary_path.stat().st_size if summary_path.exists() else 0),
             reason="human rejected the approval gate")
        print("Rejected. summary.md was NOT written.")
        sys.exit(0)


def run():
    """Top-level wrapper: guarantees a session_end trace line and a cost
    reconciliation append on every exit path, and catches any unexpected
    (non-deliberate) crash so it's still recorded before the process dies."""
    exit_code = 0
    try:
        main()
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        raise
    except Exception as e:
        exit_code = 1
        tb = traceback.format_exc()
        _log(_last_step or "unknown", "-", "", "", 0.0, "crashed", phase="end",
             error_type=type(e).__name__, error=str(e), traceback=tb)
        raise
    finally:
        _log("session_end", "-", "", "", 0.0, "exit", phase="end",
             exit_code=exit_code, total_runtime_s=round(time.time() - _SESSION_START, 3))
        append_cost_reconciliation()


if __name__ == "__main__":
    run()