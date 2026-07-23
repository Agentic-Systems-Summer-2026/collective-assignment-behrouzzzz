# Evaluation Cases — Literature Review Assistant

Legend for **Tests**: [T] = tools.py only · [E] = needs evaluator.py · [A] = needs the full agent.py loop.


## Case 1 — Simple factual question, one obvious source
**Tests:** [A] 
**Question:** "According to Liu et al. (2026), overall, how much more token usage and response time did the agent systems require compared to baseline LLMs?"
**Source:** Liu2026
**Quote:** `consistently requiring more than tenfold the token usage and at least twice the response time compared to baseline LLMs`
**Expected:** Correct source cited, quote is real, citation + reference entry both correct
**Status:** write_annotation half PASSED (verified directly); full agent-loop half still needs agent.py

## Case 2 — Same question, re-run once
**Tests:** [A] 
**Question:** (same as Case 1, run again)
**Expected:** Human reviewer confirms both runs cite Liu2026 and report the same "10x tokens / 2x latency" fact. Exact wording may differ.
**Status:** not run

## Case 3 — Question answerable by two known relevant sources
**Tests:** [A] 
**Question:** "Which two of these surveys propose a two-way classification framework for LLM/agentic AI approaches — one splitting agent paradigms into two lineages, the other splitting optimization methods into two categories?"
**Expected source_ids:** AbouAli2025 (symbolic/classical vs. neural/generative paradigms) and Du2026 (parameter-driven vs. parameter-free optimization) — References section lists both, checked directly
**Status:** not run

## Case 4 — Question with no answer in any source
**Tests:** [T] or [A]
**Question:** "What dollar cost did any of these five papers report for running their agent systems?"
**Verified:** grepped all 5 extracted texts for "$" — zero matches in any file. None of these papers report a dollar figure.
**Expected:** Agent says "not found," doesn't invent a cost
**Status:** not run

## Case 5 — Real quote exists but is off-topic
**Tests:** [E] 
**Question:** "What accuracy did the agent systems achieve on medical benchmarks?"
**Adversarial quote (real, but doesn't answer the question):** `Extended author information available on the last page of the article` (from AbouAli2025 — a real sentence, verbatim, but says nothing about accuracy)
**Expected:** Evaluator-optimizer step catches it, returns REJECT with a reason
**Status:** PASSED — real run against EVALUATOR_MODEL="Gemma4-31B": `{'ok': False, 'reason': 'The quote provides information about author details and does not mention accuracy or medical benchmarks.'}`. Case 1 also PASSED in the same run: `{'ok': True}`.

## Case 6 — Bad or nonexistent source_id passed to write_annotation
**Tests:** [T] 
**Input:** `write_annotation("not_a_real_id", "any quote", "any answer")`
**Expected:** Tool rejects it with an error, nothing gets saved
**Status:** PASSED — verified against real tools.py + real PDFs

## Case 7 — Paraphrased "quote" not literally in the source text
**Tests:** [T] 
**Input:** `write_annotation("Liu2026", "the paper says agent systems use about ten times more tokens and twice the response time than plain LLMs", "any answer")`
**Note:** This is a paraphrase of Case 1's real quote, not a copy-paste — deliberately not verbatim.
**Expected:** write_annotation rejects it
**Status:** PASSED — verified against real tools.py + real PDFs

## Case 8 — Source missing from sources.json
**Tests:** [T]
**Setup:** Temporarily drop an extra file (e.g. a copy of any PDF renamed `test_extra.pdf`) into sources/ with no matching sources.json entry, run list_sources()
**Expected:** Returned with `"id": None` — reports the gap instead of guessing author/year
**Status:** PASSED — verified against real tools.py + real PDFs

## Case 9 — Snippet search, then full read for context
**Tests:** [T] 
**Input:** `search_sources("tenfold")` then `read_source("Liu2026.pdf")` on the matching hit
**Expected:** search_sources finds the "tenfold" line in Liu2026; read_source returns the full text so the surrounding context (which benchmarks, which token counts) is available
**Status:** PASSED — verified against real tools.py + real PDFs

## Case 10 — Two similar quotes in the same source, better match decided in advance
**Tests:** [A] 
**Question:** "What overall accuracy did OpenManus achieve on MedAgentsBench?"
**Correct quote (pre-decided):** `OpenManus achieved the highest overall accuracy (30.3%)` — this is the MedAgentsBench figure
**Confusable nearby quote (same source, different benchmark):** `OM_MedAssist achieved the highest accuracy of 28.0%` — this is the MIMIC-IV figure, not MedAgentsBench
**Expected:** Agent's chosen quote is the 30.3% MedAgentsBench line, not the 28.0% MIMIC-IV line
**Status:** not run

## Case 11 — Any typical single-source question (efficiency)
**Tests:** [A]
**Question:** (reuse Case 1's question)
**Expected:** <=8 model calls and <=4,000 tokens
**Status:** not run

## Case 12 — Multi-source answer file
**Tests:** [A]
**Question:** "How does the symbolic-vs-neural paradigm split (Abou Ali et al.) relate to the parameter-driven-vs-parameter-free split (Du et al.) as two different ways of categorizing LLM agent approaches?"
**Expected source_ids:** AbouAli2025 and Du2026 only — References section lists exactly these two, nothing else
**Status:** not run

## Case 13 — Quote crossing a line break in the source PDF
**Tests:** [T]
**Source:** AbouAli2025
**Real PDF artifact confirmed:** the extracted text contains `"...but its rapid advance -\nment has led to a fragmented..."` — the word "advancement" is split by a hyphen exactly at a line break.
**Quote to test:** `its rapid advancement has led to a fragmented understanding, often conflating modern neural systems with outdated symbolic models`
**Expected:** write_annotation's normalized match still accepts it (complements Case 7, which tests the opposite failure)
**Status:** PASSED — but only after fixing a real bug: the rejoin regex originally only stripped whitespace *after* the hyphen, not *before* it. This source has "advance -\nment" (space before the hyphen too), so the first version of _normalize() produced "advance ment" (two words) instead of "advancement." Fixed in tools.py.

