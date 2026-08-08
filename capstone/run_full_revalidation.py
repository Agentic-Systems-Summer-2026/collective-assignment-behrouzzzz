"""
Day 19 mandatory live re-validation — all 13 documented cases, run against
the CURRENT code (the package with _canon, candidate_sources, the
MIN_EXPLORATION_BEFORE_GIVEUP guard, and the fixed evaluator.py timeout).

Every question/quote/setup below is copied verbatim from cases.md -- nothing
here is reworded or re-decided. Run this once from inside capstone/, paste
the ENTIRE output back.

Cost note: Cases 1, 2, 3, 4, 10, 12 each make a real live model run (agent
loop + evaluator). Case 5 makes one direct evaluator call. Cases 6, 7, 8, 9,
13 are free (tools.py only, no model). If you want to sanity-check the
environment first without spending quota, run only up to PART A below and
confirm it prints "ALL OFFLINE CASES OK" before continuing to PART B/C.

    python3 run_full_revalidation.py 2>&1 | tee revalidation_output.txt
"""
import json
import time
import traceback
from pathlib import Path

import tools

RESULTS = {}


def record(case, status, detail=""):
    RESULTS[case] = {"status": status, "detail": detail}
    print(f"\n{'='*70}\nCASE {case}: {status}\n{'='*70}")
    if detail:
        print(detail)


print("#" * 70)
print("# PART A -- offline [T] cases (no model, no cost)")
print("#" * 70)

# ---- Case 6: bad source_id ----
try:
    r = tools.verify_quote("not_a_real_id", "any quote")
    ok = r.get("ok") is False and "not_a_real_id" in r.get("error", "")
    record("6", "PASS" if ok else "FAIL", json.dumps(r))
except Exception as e:
    record("6", "ERROR", traceback.format_exc())

# ---- Case 7: paraphrase, not verbatim ----
try:
    r = tools.verify_quote(
        "Liu2026",
        "the paper says agent systems use about ten times more tokens and "
        "twice the response time than plain LLMs",
    )
    ok = r.get("ok") is False
    record("7", "PASS" if ok else "FAIL", json.dumps(r))
except Exception as e:
    record("7", "ERROR", traceback.format_exc())

# ---- Case 8: source on disk, missing from sources.json ----
try:
    extra = Path(tools.SOURCES_DIR) / "test_extra.pdf"
    any_pdf = next(p for p in Path(tools.SOURCES_DIR).iterdir() if p.suffix == ".pdf")
    extra.write_bytes(any_pdf.read_bytes())
    tools._TEXT_CACHE.clear()
    listed = tools.list_sources()
    row = next((x for x in listed if x["file"] == "test_extra.pdf"), None)
    ok = row is not None and row["id"] is None
    record("8", "PASS" if ok else "FAIL", json.dumps(row))
except Exception:
    record("8", "ERROR", traceback.format_exc())
finally:
    try:
        extra.unlink(missing_ok=True)
        tools._TEXT_CACHE.clear()
    except Exception:
        pass

# ---- Case 9: search then read ----
try:
    hits = tools.search_sources("tenfold")
    hit_list = hits.get("hits", hits) if isinstance(hits, dict) else hits
    found_liu = any(h.get("file") == "Liu2026.pdf" for h in hit_list)
    full = tools.read_source("Liu2026.pdf")
    ok = found_liu and full.get("ok") is True and len(full.get("text", "")) > 1000
    record("9", "PASS" if ok else "FAIL",
           f"search hits: {len(hit_list)}, found in Liu2026: {found_liu}, "
           f"read_source ok: {full.get('ok')}, len: {len(full.get('text', ''))}")
except Exception:
    record("9", "ERROR", traceback.format_exc())

# ---- Case 13: quote crossing a line break ----
try:
    r = tools.verify_quote(
        "AbouAli2025",
        "its rapid advancement has led to a fragmented understanding, often "
        "conflating modern neural systems with outdated symbolic models",
    )
    ok = r.get("ok") is True
    record("13", "PASS" if ok else "FAIL", json.dumps(r))
except Exception:
    record("13", "ERROR", traceback.format_exc())

offline_ok = all(RESULTS[c]["status"] == "PASS" for c in ("6", "7", "8", "9", "13"))
print(f"\n{'#'*70}")
print(f"# {'ALL OFFLINE CASES OK' if offline_ok else 'OFFLINE CASES HAD FAILURES -- STOP AND CHECK BEFORE SPENDING LIVE QUOTA'}")
print(f"{'#'*70}\n")

print("#" * 70)
print("# PART B -- Case 5, direct evaluator call (1 model call)")
print("#" * 70)
try:
    from evaluator import evaluate
    r = evaluate(
        question="What accuracy did the agent systems achieve on medical benchmarks?",
        quote="Extended author information available on the last page of the article",
        source_id="AbouAli2025",
    )
    ok = r.get("ok") is False and not r.get("technical_error")
    record("5", "PASS" if ok else "FAIL", json.dumps(r))
except Exception:
    record("5", "ERROR", traceback.format_exc())

print("#" * 70)
print("# PART C -- full agent loop, 6 cases (live model + evaluator each)")
print("#" * 70)

from agent import answer_question

CASE1_Q = ("According to Liu et al. (2026), overall, how much more token usage "
           "and response time did the agent systems require compared to baseline LLMs?")

full_loop_cases = [
    ("1", CASE1_Q),
    ("2", CASE1_Q),  # same question, re-run -- human/manual check: same source cited?
    ("3", "Which two of these surveys propose a two-way classification framework for "
          "LLM/agentic AI approaches — one splitting agent paradigms into two lineages, "
          "the other splitting optimization methods into two categories?"),
    ("4", "What dollar cost did any of these five papers report for running their agent systems?"),
    ("10", "What overall accuracy did OpenManus achieve on MedAgentsBench?"),
    ("12", "How does the symbolic-vs-neural paradigm split (Abou Ali et al.) relate to the "
           "parameter-driven-vs-parameter-free split (Du et al.) as two different ways of "
           "categorizing LLM agent approaches?"),
]

for case_id, question in full_loop_cases:
    print(f"\n----- starting Case {case_id} -----")
    t0 = time.time()
    try:
        answer = answer_question(question, verbose=True)
        dt = time.time() - t0
        record(case_id, "SEE OUTPUT ABOVE -- check against cases.md's pass criteria",
               f"answer: {answer}\nelapsed: {dt:.1f}s")
    except Exception:
        record(case_id, "ERROR", traceback.format_exc())

print("\n\n" + "#" * 70)
print("# SUMMARY -- paste everything from here up, plus the full output above, back")
print("#" * 70)
for case_id in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "13"]:
    r = RESULTS.get(case_id, {"status": "NOT RUN"})
    print(f"  Case {case_id:>2}: {r['status']}")
print("\nCase 11 (efficiency ceiling) is derived from Case 1's own logged token/call count above, not a separate run.")
print("\nAlso paste: the contents of the newest 6 files in capstone/logs/ (one per full-loop case above).")
