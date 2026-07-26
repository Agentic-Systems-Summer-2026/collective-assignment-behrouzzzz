# Evaluation Cases — Literature Review Assistant

The 13 test cases from PROPOSAL.md Section 4, filled in with real questions and real verbatim quotes I pulled directly from the 5 attached PDFs (using the same pypdf extraction tools.py uses, so quotes match what the tool will actually see). Nothing here is guessed — every quote below was verified with a grep against the extracted text before being written in.

Sources on hand: AbouAli2025, Du2026, Liu2026, Qin2026, Xi2025.

Legend for **Tests**: [T] = tools.py only · [E] = needs evaluator.py · [A] = needs the full agent.py loop.

---

## Case 1 — Simple factual question, one obvious source
**Tests:** [A] full loop
**Question:** "According to Liu et al. (2026), overall, how much more token usage and response time did the agent systems require compared to baseline LLMs?"
**Source:** Liu2026
**Expected:** Correct source cited, quote is real, citation + reference entry both correct
**Status:** PASSED — full loop, real API, real answer:
```
According to Liu et al. (2026), agent systems required more than 10× token usage and more than 2× latency compared to baseline LLMs.
```
Citation: Liu2026. Quote used: `>10× token usage and >2× latency. Although 89.9% of hallucinations were filtered by in-agent safeguards, hallucinations remained prevalent.` — a different real sentence from the source than the one originally planned for this case (`...requiring more than tenfold...`), found and used by the agent itself; both sentences say the same thing and both are real, verbatim text from Liu2026.

Took 7 of 8 turns (1 list_sources, 3 search_sources, 1 read_source, then finish — no wasted rejection cycles). Real cost: 7 model calls, 12,597 tokens, 1 cache hit. Two real bugs were found and fixed to get this run working, both from live-model behavior that stub tests couldn't surface:
1. A JSON-extraction bug (`re.search(r"\{.*\}")` was greedy and grabbed trailing text past the first JSON object whenever the model's raw output had a stray `}` later on) — fixed by switching to `json.JSONDecoder().raw_decode()`, which reads only the first complete JSON value and ignores anything after it.
2. A token-cost blow-up: `read_source` returning a full ~60,000-character PDF, which then sat in the conversation history and got re-sent on every subsequent turn, driving one run to 122,023 tokens for a single question. Fixed by truncating `read_source`'s returned text to 4,000 characters (with a `"truncated": true` flag telling the model to fall back to `search_sources` for anything past that).

**Open item:** actual cost (12,597 tokens) is well above the ≤4,000-token ceiling PROPOSAL.md's Case 11 assumed before any real run existed. That ceiling should be revised with this real number rather than left as an unmet target — see Case 11 below.

**Re-run against the claim-level `finish` redesign:** found the correct quote again and called `finish` correctly on the last available turn (8/8) — but the evaluator's live network call timed out, and because the turn cap was checked against the raw step count, the technical failure (correctly excluded from the rejection budget) still consumed the run's last turn, producing `INSUFFICIENT CONTEXT` despite a fully correct, verbatim-matched quote. Real, live-model-only bug, fixed by decoupling the turn cap from purely-technical `finish` failures. A small pool of free technical retries no longer costs a turn, up to `MAX_TECHNICAL_FINISH_RETRIES = 3` per run.

**Second re-run, same question:** the turn/budget fix worked correctly (no turn or rejection was charged for the timeout) — but the run still failed, because the model was given the free retry as a *turn* (an observation to react to) and, instead of resubmitting the same claim, went searching for a new quote phrasing, which burned the run's actual last turn on a redundant search. Fixed by not routing purely-technical failures through the model at all — they're now retried silently in-process.

**Third and fourth re-runs, same question:** the in-process retry mechanism itself worked exactly as designed (3 free retries, no turn/budget cost) — but kept failing anyway, because `EVALUATOR_MODEL="GLM 5.2"` (original default) turned out to be genuinely unreachable on the course sandbox (8 real network attempts, all timing out identically), not just a one-off blip. Swapping to `"Claude Haiku 3"` surfaced a *different*, non-technical problem: an explicit 404 from the course's Bedrock backend saying that model is deprecated/legacy and access was revoked. Swapping again to `"Gemma4-31B"` (already confirmed working earlier, in Case 5) **finally succeeded end-to-end for real**: correct source (Liu2026), correct verbatim quote, evaluator ACCEPT on the first attempt, 0 technical retries needed, answer file written. This is the first real, live confirmation that the full claim-level redesign (finish schema, turn-budget decoupling, in-process technical retry) works correctly outside of stub tests. `evaluator.py`'s default `EVALUATOR_MODEL` updated to `"Gemma4-31B"` accordingly.

**Root-cause note:** none of the last several real failures were bugs in `agent.py` — they were all a broken/deprecated evaluator model choice. The turn-budget and in-process-retry fixes are still correct and worth keeping (a real evaluator hiccup will happen again eventually), but the actual blocker this whole time was picking a dead model for `EVALUATOR_MODEL`.

## Case 2 — Same question, re-run once
**Tests:** [A] full loop
**Question:** (same as Case 1, run again)
**Expected:** Human reviewer confirms both runs cite Liu2026 and report the same "10x tokens / 2x latency" fact. Exact wording may differ.
**Status:** PASSED — real run, `EVALUATOR_MODEL="Gemma4-31B"`. Same source (Liu2026), same core fact as Case 1. Also stress-tested the in-process technical retry for real: hit 3 consecutive evaluator timeouts, succeeded silently on the 3rd retry with zero model turns spent on it.

## Case 3 — Question answerable by two known relevant sources
**Tests:** [A] full loop
**Question:** "Which two of these surveys propose a two-way classification framework for LLM/agentic AI approaches — one splitting agent paradigms into two lineages, the other splitting optimization methods into two categories?"
**Expected source_ids:** AbouAli2025 (symbolic/classical vs. neural/generative paradigms) and Du2026 (parameter-driven vs. parameter-free optimization) — References section lists both, checked directly
**Status:** PASSED — real run. Both source_ids present in the final answer. This is also the first real confirmation of incremental per-claim locking: the Du2026 claim failed once (non-verbatim quote) and was corrected on a second `finish` call, while the already-accepted AbouAli2025 claim was never resubmitted or re-verified in that second call. Cost: 17 calls, 62,581 tokens (multi-source, so the dynamic turn cap correctly scaled to 16).

## Case 4 — Question with no answer in any source
**Tests:** [T] or [A]
**Question:** "What dollar cost did any of these five papers report for running their agent systems?"
**Verified:** grepped all 5 extracted texts for "$" — zero matches in any file. None of these papers report a dollar figure.
**Expected:** Agent says "not found," doesn't invent a cost
**Status:** PASSED — confirmed on a real run against the current code. The agent submitted three grounded claims about *computational* cost (token cost, an efficiency imbalance, RL compute) and the evaluator rejected all three with explicit `(Check 2 failed)` reasons — e.g. "it discusses general limitations regarding token cost rather than reporting a specific dollar cost". Final answer: `INSUFFICIENT CONTEXT`, zero claims accepted, no cost invented. This is the first live confirmation that the `original_question` relevance check works end to end. Note an honest cost: the improved retrieval makes this negative case *harder*, not easier — the old barren searches made "nothing here" obvious, whereas queries like `expense` and `computational cost` now return real, on-topic-sounding material and tempt the model into submitting it (21 calls / 101,318 tokens, up from 11 / 61,265). Retrieval created the temptation; the evaluator caught it. Neither layer alone would have been enough.

## Case 5 — Real quote exists but is off-topic
**Tests:** [E] evaluator — ready to run now, evaluator.py is built
**Question:** "What accuracy did the agent systems achieve on medical benchmarks?"
**Adversarial quote (real, but doesn't answer the question):** `Extended author information available on the last page of the article` (from AbouAli2025 — a real sentence, verbatim, but says nothing about accuracy)
**Expected:** Evaluator-optimizer step catches it, returns REJECT with a reason
**Status:** PASSED — real run against EVALUATOR_MODEL="Gemma4-31B": `{'ok': False, 'reason': 'The quote provides information about author details and does not mention accuracy or medical benchmarks.'}`. Case 1 also PASSED in the same run: `{'ok': True}`.

## Case 6 — Bad or nonexistent source_id
**Tests:** [T] — run now
**Input:** `verify_quote("not_a_real_id", "any quote")`
**Expected:** Tool rejects it with an error, nothing gets saved
**Status:** PASSED — re-verified against real tools.py (post-refactor) + real PDFs

## Case 7 — Paraphrased "quote" not literally in the source text
**Tests:** [T] — run now
**Input:** `verify_quote("Liu2026", "the paper says agent systems use about ten times more tokens and twice the response time than plain LLMs")`
**Note:** This is a paraphrase of Case 1's real quote, not a copy-paste — deliberately not verbatim.
**Expected:** verify_quote rejects it
**Status:** PASSED — re-verified against real tools.py (post-refactor) + real PDFs

## Case 8 — Source missing from sources.json
**Tests:** [T] — run now
**Setup:** Temporarily drop an extra file (e.g. a copy of any PDF renamed `test_extra.pdf`) into sources/ with no matching sources.json entry, run list_sources()
**Expected:** Returned with `"id": None` — reports the gap instead of guessing author/year
**Status:** PASSED — re-verified against real tools.py (post-refactor) + real PDFs

## Case 9 — Snippet search, then full read for context
**Tests:** [T] — run now
**Input:** `search_sources("tenfold")` then `read_source("Liu2026.pdf")` on the matching hit
**Expected:** search_sources finds the "tenfold" line in Liu2026; read_source returns the full text so the surrounding context (which benchmarks, which token counts) is available
**Status:** PASSED — re-verified against real tools.py (post-refactor) + real PDFs

## Case 10 — Two similar quotes in the same source, better match decided in advance
**Tests:** [A] full loop
**Question:** "What overall accuracy did OpenManus achieve on MedAgentsBench?"
**Correct quote (pre-decided):** `OpenManus achieved the highest overall accuracy (30.3%)` — this is the MedAgentsBench figure
**Confusable nearby quote (same source, different benchmark):** `OM_MedAssist achieved the highest accuracy of 28.0%` — this is the MIMIC-IV figure, not MedAgentsBench
**Expected:** Agent's chosen quote is the 30.3% MedAgentsBench line, not the 28.0% MIMIC-IV line
**Status:** PASSED — real run, answer `30.3%`. Worth recording how it got there: the agent first quoted the body sentence ("On the complete 862-item MedAgentsBench HARD set, OpenManus achieved 30.3% accuracy...") and, when that attempt failed, switched from the same search results to a more precise quote that says `overall accuracy` in as many words. That second quote only appears in the results because all-terms matching spans adjacent sentences: the figure caption names the benchmark in one sentence and reports the number in the next, so single-sentence matching never surfaced it.

## Case 11 — Any typical single-source question (efficiency)
**Tests:** [A] full loop — call/token counting now wired into agent.py (per-run `usage` in every log)
**Question:** (reuse Case 1's question)
**Original expected ceiling:** <=8 model calls and <=4,000 tokens (written before any real run existed)
**Real result (from Case 1's run):** 7 calls, 12,597 tokens, 1 cache hit — within the 8-call budget, but ~3x over the original token guess.
**Revised expected ceiling:** <=8 model calls and <=15,000 tokens. The call budget was right; the token guess wasn't — a `read_source` call alone costs roughly 1,000+ tokens per turn it stays in history (even truncated to 4,000 characters), and a typical run touches it once. 
**Status:** PASSED, and now with margin. Two real runs of Case 1's question against the current code both used **1 model call** (ceiling 8). Reported tokens were 658 and 663, but both runs had 4 cache hits, so those figures are NOT a cold-start cost and should not be compared directly against the original 12,597 — the trustworthy number here is the call count. 

## Case 12 — Multi-source answer file
**Tests:** [A] full loop (one `finish` call carrying citations from both sources — no longer two separate write_annotation calls needing identical answer_text)
**Question:** "How does the symbolic-vs-neural paradigm split (Abou Ali et al.) relate to the parameter-driven-vs-parameter-free split (Du et al.) as two different ways of categorizing LLM agent approaches?"
**Expected source_ids:** AbouAli2025 and Du2026 only — References section lists exactly these two, nothing else
**Status:** PASSED — real run, both `AbouAli2025` and `Du2026` accepted, References lists exactly those two. The earlier diagnosis recorded here was **wrong**, and the log says so plainly: the fix was not a nudge to re-read already-fetched text. In the passing run the agent searched the very question-derived phrases that had always returned nothing — `symbolic-vs-neural paradigm` at step 2 and `parameter-driven-vs-parameter-free` at step 3, and both returned hits this time. The blocker was never the model's strategy. It was that search tokenised a hyphenated phrase as one indivisible blob, so a multi-concept query could never match. Chasing the prompt-level hypothesis first cost two regressions before the retrieval layer was measured.

## Case 13 — Quote crossing a line break in the source PDF
**Tests:** [T] — run now
**Source:** AbouAli2025
**Real PDF artifact confirmed:** the extracted text contains `"...but its rapid advance -\nment has led to a fragmented..."` — the word "advancement" is split by a hyphen exactly at a line break.
**Quote to test:** `its rapid advancement has led to a fragmented understanding, often conflating modern neural systems with outdated symbolic models`
**Expected:** verify_quote's normalized match still accepts it (complements Case 7, which tests the opposite failure)
**Status:** PASSED — fixed a real bug (rejoin regex only stripped whitespace *after* the hyphen, not before; this source has "advance -\nment" with a space on both sides). Re-verified against real tools.py (post-refactor) + real PDFs.


