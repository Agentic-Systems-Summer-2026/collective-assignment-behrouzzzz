"""
Offline regression test for the crash-safe per-event trace logging added to
agent.py (ported from the BC5 observability build challenge's pattern; see
Knowledge_Base.md Section 6 and Open_Issues.md for the gap this closes).

Two things are verified, with no live model and no quota:

1. A normal, successful run behaves identically to before this change
   (same final answer, same public function signature), and produces the
   expected sequence of trace events in logs/<run_id>.trace.jsonl.
2. An uncaught exception from the generator's chat() call is recorded as a
   single "crashed" trace event with the exception type and a traceback,
   followed by a "session_end" event, and the exception still propagates
   to the caller unchanged (this test does not weaken error visibility --
   it only proves the crash is no longer silently unlogged).

Run from this directory:  python3 test_trace_logging.py
"""
import json
import sys
from pathlib import Path

import agent

fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if detail:
        print(f"          {detail}")
    if not cond:
        fails.append(name)


def read_trace_events(trace_path: Path):
    events = []
    with trace_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def find_trace_path_for_run(before_files: set) -> Path:
    """The run_id (and therefore the trace filename) is generated inside
    answer_question() and not returned to the caller, so tests locate the
    new file the same way a human would: by diffing the logs directory
    before and after the call."""
    after_files = set(agent.LOG_DIR.glob("*.trace.jsonl"))
    new_files = after_files - before_files
    assert len(new_files) == 1, f"expected exactly 1 new trace file, found {len(new_files)}"
    return new_files.pop()


# ---------------------------------------------------------------------------
print("\n[1] Normal successful run: same behavior, plus correct trace events")

def fake_chat_normal(msgs, cache=False):
    calls_normal["i"] += 1
    i = calls_normal["i"]
    if i == 1:
        # guard should reject this: zero exploration attempts so far
        return json.dumps({"tool": "finish", "answer": "INSUFFICIENT CONTEXT"})
    if i == 2:
        return json.dumps({"tool": "search_sources", "query": "token usage"})
    return json.dumps({"tool": "finish", "answer": "INSUFFICIENT CONTEXT"})


calls_normal = {"i": 0}
agent.chat = fake_chat_normal
agent.tools.search_sources = lambda query: {"ok": True, "hits": [], "total_hits": 0, "match_mode": "terms"}

agent.LOG_DIR.mkdir(parents=True, exist_ok=True)
before = set(agent.LOG_DIR.glob("*.trace.jsonl"))
answer = agent.answer_question("What dollar cost did any of these five papers report?", verbose=False)
trace_path = find_trace_path_for_run(before)
events = read_trace_events(trace_path)

check("returns the correct final answer, same as before this change",
      "INSUFFICIENT CONTEXT" in answer, f"answer: {answer!r}")

steps = [(e["step"], e["phase"]) for e in events]
check("trace opens with run/start",
      steps[0] == ("run", "start"), f"first event: {steps[0]}")
check("trace closes with run/session_end",
      steps[-1] == ("run", "session_end"), f"last event: {steps[-1]}")
check("session_end records outcome=completed",
      events[-1].get("outcome") == "completed", f"outcome: {events[-1].get('outcome')}")
check("3 generator turns each produced a start/end pair (6 generator events)",
      sum(1 for s in steps if "generator" in s[0]) == 6,
      f"generator-related events: {[s for s in steps if 'generator' in s[0]]}")
check("the search_sources tool call was traced (start and end)",
      sum(1 for s in steps if "tool_search_sources" in s[0]) == 2,
      f"tool events: {[s for s in steps if 'tool' in s[0]]}")
generator_ends = [e for e in events if e["phase"] == "end" and "generator" in e["step"]]
check("every generator end event recorded decision=success and a latency",
      all(e.get("decision") == "success" and "latency_s" in e for e in generator_ends),
      f"{generator_ends}")

# The existing summary log (unchanged format) should also still be written,
# and its filename should share the trace file's run_id base.
summary_path = trace_path.with_suffix("").with_suffix(".json")
check("the existing per-run summary JSON log is still written, same run_id",
      summary_path.exists(), f"expected: {summary_path}")

# ---------------------------------------------------------------------------
print("\n[2] Uncaught crash: recorded, then still raised, never silently lost")

class SimulatedNetworkFailure(RuntimeError):
    pass


def fake_chat_crashes(msgs, cache=False):
    raise SimulatedNetworkFailure("simulated: generator model unreachable")


agent.chat = fake_chat_crashes

before2 = set(agent.LOG_DIR.glob("*.trace.jsonl"))
raised = None
try:
    agent.answer_question("Any question -- this run is designed to crash on turn 1.", verbose=False)
except SimulatedNetworkFailure as e:
    raised = e

check("the exception still propagates to the caller, unchanged and unswallowed",
      raised is not None and "unreachable" in str(raised))

trace_path2 = find_trace_path_for_run(before2)
events2 = read_trace_events(trace_path2)
steps2 = [(e["step"], e["phase"]) for e in events2]

check("trace opens with run/start",
      steps2[0] == ("run", "start"))
check("the failing generator call was recorded as a failed end event",
      any(e["step"] == "turn_1_generator" and e["phase"] == "end" and e.get("decision") == "failed"
          for e in events2))
check("a run/crashed event was recorded, with the exception type and a traceback",
      any(e["step"] == "run" and e["phase"] == "crashed"
          and e.get("error_type") == "SimulatedNetworkFailure"
          and "traceback" in e and "SimulatedNetworkFailure" in e["traceback"]
          for e in events2))
check("trace still closes with run/session_end even though the run crashed",
      steps2[-1] == ("run", "session_end"))
check("session_end records outcome=crashed",
      events2[-1].get("outcome") == "crashed", f"outcome: {events2[-1].get('outcome')}")

# Before this change, a crash here produced NO log file at all -- this is
# the actual gap being closed, stated as an explicit, checkable assertion.
check("(the gap this test exists for) a trace file exists at all for a crashed run",
      trace_path2.exists() and len(events2) > 0)

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILURES'}\n")
sys.exit(1 if fails else 0)
