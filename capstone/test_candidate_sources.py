"""
Offline tests for stage-3 candidate-source discovery in search_sources.

Three things this must prove, per the checkpoint discussion:
  1. A real vocabulary-gap question (user says "cost", source says
     "computational resources"/"GPU utilization") gets zero exact/terms
     hits but DOES get ranked candidates.
  2. Candidates are ranked by matched-term count, highest first -- not an
     unordered list.
  3. A query with genuinely no shared vocabulary anywhere in the corpus
     gets zero candidates, not a plausible-looking guess. This is the
     control that proves the mechanism doesn't manufacture confidence
     out of nothing.

No model call anywhere in this file.
"""
import sys

import tools

fails = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if detail:
        print(f"          {detail}")
    if not cond:
        fails.append(name)


print("\n[1] Vocabulary-gap question: zero exact match, but candidates found")
r = tools.search_sources("cost to operate the model")
check("no exact phrase or all-terms hit", r["total_hits"] == 0 and not r["hits"])
check("candidate_sources present", "candidate_sources" in r,
      f"keys: {sorted(r.keys())}")
files = [c["file"] for c in r.get("candidate_sources", [])]
check("at least one candidate has real, on-topic vocabulary overlap",
      any(len(c["matched_terms"]) >= 2 for c in r.get("candidate_sources", [])),
      str(r.get("candidate_sources")))
check("note makes clear this is a suggestion, not evidence of an answer",
      "not evidence" in r.get("note", "").lower() or "worth reading" in r.get("note", "").lower(),
      r.get("note", "")[:100])

print("\n[2] Candidates are ranked, not just listed")
r2 = tools.search_sources("MedAgentsBench clinical diagnosis hospital patient")
scores = [len(c["matched_terms"]) for c in r2.get("candidate_sources", [])]
check("scores present and non-trivial", len(scores) >= 2, str(scores))
check("sorted highest-overlap first", scores == sorted(scores, reverse=True), str(scores))
check("no raw internal score field leaked (matched_terms is the public signal)",
      all("score" not in c for c in r2.get("candidate_sources", [])))

print("\n[3] Control: vocabulary genuinely absent from the whole corpus")
absent = ["xylophone", "marmalade", "kangaroo", "volcano", "trombone", "cinnamon"]
# Verify the control words really are absent before trusting the result --
# an untested control proves nothing.
really_absent = all(
    w not in tools._canon(text) for w in absent for _, text in tools._iter_sources()
)
check("control words are genuinely absent from the corpus (test validity check)",
      really_absent)
r3 = tools.search_sources(" ".join(absent))
check("zero hits", r3["total_hits"] == 0)
check("zero candidates -- no manufactured guess for truly missing vocabulary",
      "candidate_sources" not in r3 or not r3["candidate_sources"],
      str(r3.get("candidate_sources")))

print("\n[4] A real exact/terms hit is unaffected (candidates only fire on total silence)")
r4 = tools.search_sources("token usage")
check("normal hit path still works", r4["total_hits"] > 0 and r4["hits"])
check("no candidate_sources noise on a query that already found something",
      "candidate_sources" not in r4)

print("\n[5] Candidate list is capped, not an unbounded corpus browse")
r5 = tools.search_sources("model cost accuracy benchmark evaluation")
check(f"capped at {tools.CANDIDATE_SOURCES_MAX}",
      len(r5.get("candidate_sources", [])) <= tools.CANDIDATE_SOURCES_MAX,
      f"{len(r5.get('candidate_sources', []))} returned")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILURES: ' + ', '.join(fails)}\n")
sys.exit(1 if fails else 0)
