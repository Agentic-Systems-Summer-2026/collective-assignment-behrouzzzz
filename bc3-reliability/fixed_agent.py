#!/usr/bin/env python3
"""Build Challenge 3 — FIXED agent.

Run from the repo root:  python3 bc3-reliability/fixed_agent.py

Fixes over broken_agent.py:
  1. Uses common.llm.chat() — no internal _key / BASE / DEFAULT_MODEL access.
  2. Per-call timeout (10 s) with up to 3 retry attempts and exponential backoff.
  3. Code-fence stripping + JSON validation; bad replies are recorded, not fatal.
  4. Atomic report write: new results go to a temp file; it replaces the real
     report only after the full run succeeds (last good report is never lost).
  5. Checkpoint file: every finished item (pass or fail) is saved immediately so
     a Codespace restart resumes instead of reprocessing from the top.
  6. Every failure is logged with its id and reason — no silent except: pass.
  7. Honest end-of-run summary (approved / failed counts).
  8. Re-running after a complete successful run is idempotent: all items are
     already in the checkpoint so the script exits cleanly with zero new work.
"""
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat  # noqa: E402  (sys.path insert must come first)

HERE = pathlib.Path(__file__).resolve().parent
REQUESTS_FILE = HERE / "requests.jsonl"
REPORT        = HERE / "approved_report.md"
REPORT_TMP    = HERE / "approved_report.md.tmp"
CHECKPOINT    = HERE / "checkpoint.jsonl"
ERROR_LOG     = HERE / "error_log.txt"

CLASSIFY_PROMPT = (
    'Classify this change request. Reply ONLY with JSON '
    '{"risk": "low|medium|high", "reason": "<one line>"}\n\n'
)

TIMEOUT_SECS   = 10
MAX_ATTEMPTS   = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers and surrounding whitespace."""
    text = text.strip()
    # Remove opening fence (```json or ```)
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    # Remove closing fence
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def classify_with_retry(request_text: str) -> dict:
    """
    Call the model, parse JSON, retry on timeout/error or bad JSON.
    Returns {"risk": ..., "reason": ...} or raises RuntimeError after all attempts.
    """
  
    messages = [{"role": "user", "content": CLASSIFY_PROMPT + request_text}]
    last_error = None

    for attempt in range(MAX_ATTEMPTS):
        try:
            raw = chat(messages, max_tokens=200, temperature=0, timeout=TIMEOUT_SECS)
            cleaned = strip_fences(raw)
            verdict = json.loads(cleaned)
            # Validate expected shape
            if "risk" not in verdict or "reason" not in verdict:
                raise ValueError(f"Missing 'risk' or 'reason' key: {cleaned!r}")
            return verdict
        except Exception as exc:
            last_error = exc
            wait = 2 ** attempt  # 1 s, 2 s, 4 s
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(wait)

    raise RuntimeError(f"All {MAX_ATTEMPTS} attempts failed: {last_error}") from last_error


def load_checkpoint() -> dict:
    """Return {id: result_dict} for every item already processed."""
    done = {}
    if CHECKPOINT.exists():
        for line in CHECKPOINT.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                done[entry["id"]] = entry
            except Exception:
                pass  # malformed checkpoint line — treat as not done
    return done


def append_checkpoint(entry: dict) -> None:
    """Append one finished result to the checkpoint file immediately."""
    with CHECKPOINT.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def log_error(item_id: str, reason: str) -> None:
    """Append one failure line to the error log."""
    line = f"[FAILED] {item_id}: {reason}\n"
    print(line, end="", file=sys.stderr)
    with ERROR_LOG.open("a") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load all requests
    items = [
        json.loads(line)
        for line in REQUESTS_FILE.read_text().splitlines()
        if line.strip()
    ]

    # Load what we already finished (from a previous run or interrupted run)
    done = load_checkpoint()
    pending = [item for item in items if item["id"] not in done]

    if not pending:
        # All items were already processed — just rebuild the report and exit.
        print("All items already processed (checkpoint complete). Rebuilding report.")
    else:
        print(f"Resuming: {len(done)} already done, {len(pending)} to process.")

    # Process pending items, appending checkpoint entries as we go
    for item in pending:
        item_id = item["id"]
        print(f"Processing {item_id}...")
        try:
            verdict = classify_with_retry(item["request"])
            entry = {
                "id": item_id,
                "request": item["request"],
                "risk": verdict["risk"],
                "reason": verdict["reason"],
                "status": "ok",
            }
        except Exception as exc:
            reason = str(exc)
            log_error(item_id, reason)
            entry = {
                "id": item_id,
                "request": item["request"],
                "risk": None,
                "reason": reason,
                "status": "failed",
            }
        done[item_id] = entry
        append_checkpoint(entry)

    # Build the new report from all results (preserving original item order)
    approved = []
    failed   = []
    for item in items:
        entry = done[item["id"]]
        if entry["status"] == "ok" and entry["risk"] == "low":
            approved.append(entry)
        elif entry["status"] != "ok":
            failed.append(entry)

    # Write to a temp file first; only swap when fully written
    report_lines = ["# Approved Changes\n\n"]
    for e in approved:
        report_lines.append(
            f"- **{e['id']}** (low): {e['request'][:80]} — {e['reason']}\n"
        )
    REPORT_TMP.write_text("".join(report_lines))
    # Atomic rename: replaces REPORT only after the temp write succeeds
    REPORT_TMP.replace(REPORT)

    # Honest summary
    print(f"\n{'='*50}")
    print(f"  Approved (low-risk): {len(approved)}")
    print(f"  Failed / skipped:    {len(failed)}")
    print(f"  Report written to:   {REPORT.name}")
    if failed:
        print(f"  Error log:           {ERROR_LOG.name}")
        for e in failed:
            print(f"    ✗ {e['id']}: {e['reason']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
