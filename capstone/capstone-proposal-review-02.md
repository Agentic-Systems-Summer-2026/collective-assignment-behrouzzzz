# Capstone Design Review & Progress Checkpoint — Literature Review Assistant with Citations

## 1. Scoped Use Case

I provide the agent with a folder of source documents plus a `sources.json` file exported from Zotero, including reference metadata.

**Does:** The agent answers a specific question about them, including a citation and a supporting quote. Each answer is written to a separate file, with a References section.

**Does not:** The agent does not search the web or discover new sources, decide which sources belong in the set (I choose that up front). It also does not handle scanned or image-only PDFs.

Corpus in use right now: 5 sources (AbouAli2025, Du2026, Liu2026, Qin2026, Xi2025), all surveys/benchmarks on LLM-based agents — the same set feeding my literature review, so the two assignments do real double duty.

## 2. Architecture

**Setup (human, before the loop runs):** I select the source documents and export their bibliographic metadata from Zotero as CSL-JSON into `sources.json`.

**The loop:** Given a question, the agent picks one tool at a time and decides its own sequence out of five tools (Section 3). It stops when it has an answer or hits the turn cap (8 turns).

**Evaluator-optimizer check:** Before the agent is allowed to save an answer, a separate model call checks whether the proposed quote actually answers the question. This call goes to a **different model family** than the generator, picked through an `EVALUATOR_MODEL` environment variable (same pattern as `COURSE_MODEL` in Build Challenge 2), so the evaluator does not share the generator's blind spots. If the evaluator rejects the answer, the reason is fed back into the loop as another turn.

**Turn budget rule:** The main loop keeps its 8-turn cap. The evaluator has its own separate budget: up to 2 content-based rejections. A network or timeout failure when calling the evaluator gets one technical retry, tracked separately from the 2 content rejections (mirrors the retry pattern from Build Challenge 3). If either cap is hit first, the run stops: nothing is saved, and the failure is reported with its last reason.

**One question, one answer file rule:** The user expects exactly one output file per question, always — never split across several files, even when the answer draws on facts from multiple sources. `write_annotation` groups by `answer_text` (same text → same file, so repeated calls accumulate References together); enforcing "one file per question" is the loop's job, not the tool's. The agent must build a single, synthesized `answer_text` first, then call `write_annotation` once per supporting `(source_id, quote)` pair using that *same* `answer_text` — never treat different facts or sources as separate "answers."

**Where control lives:** The model decides which tool to call and when — that judgment is the reason this is an agent rather than a fixed workflow. But several things are hard-coded, not left to the model: the turn cap, the evaluator's separate retry budget, the one-file-per-question rule above, and the fact that the agent has no tool capable of writing directly to the final bibliography document.

**Human approval gate:** After the loop finishes, I open the draft annotation file to confirm both that the quote actually supports the claim and that the citation is correct.

## 3. Tools

| Tool | What it does |
|---|---|
| `list_sources()` | Reads the source folder and cross-references `sources.json` internally; returns each file's name with its `source_id`. A file missing from `sources.json` is still listed, flagged instead of guessed. |
| `search_sources(query)` | Snippet search across all documents (BC1's snippet-search pattern), keeps token costs down versus dumping full text. |
| `read_source(name)` | Full text of one named document, for when a snippet isn't enough context. |
| `lookup_citation(source_id)` | Returns exactly two things for one source only — in-text form and reference entry. Never leaks info about other sources. |
| `write_annotation(source_id, quote, answer_text)` | The integrity gate. Verifies `source_id` exists and `quote` appears verbatim (after normalization) in that source before saving anything. |

## 4. Design Rationale — Trade-offs Considered and Defended

**Turn budget for the evaluator.** *Considered:* raise the main 8-turn cap to absorb evaluator retries, vs. give the evaluator its own separate budget. *Chose:* separate budget (2 content rejections + 1 technical retry, tracked apart from the 8-turn cap). *Why:* raising the shared cap would let a flaky evaluator silently eat into the generator's budget; keeping them separate means a technical failure and a content disagreement are diagnosed differently, and the original turn-cap guardrail from earlier build challenges stays intact instead of being loosened.

**Quote matching strictness.** *Considered:* fuzzy/semantic matching for quotes (to survive PDF extraction noise) vs. strict exact-match after normalization. *Chose:* exact match, but normalize whitespace, curly quotes, ligatures, and hyphenated line breaks first. *Why:* fuzzy matching could let a paraphrase slip through as if it were a verbatim quote — which defeats the entire point of a citation-accuracy tool. Two real extraction bugs (ligature characters, hyphen-before-linebreak) were found and fixed this way, without ever loosening the match itself.

**Second live API dependency (the evaluator).** *Considered:* skip a second live service and keep everything local/file-based, vs. add one. *Chose:* add exactly one — the cross-model evaluator — rather than bolting on an unrelated service like web search. *Why:* this directly fixes an already-known weakness (an evaluator sharing the generator's blind spots) instead of adding risk for its own sake; adding live web search, by contrast, would undercut the human-curated-source-set trust model that is central to this project's citation-accuracy story.

**Which two components to build and verify first.** *Considered:* build breadth-first (a thin version of all 5 tools) vs. depth-first on the two components identified as highest-risk in review feedback (`write_annotation`'s groundedness check, and the evaluator-optimizer). *Chose:* depth-first on those two. *Why:* these two are the actual integrity guarantees of the system — everything else (search, listing, citation lookup) is retrieval convenience. Verifying these two against real data first, before wiring the full loop, is what actually surfaced the two extraction bugs below; building all 5 shallowly first would likely have hidden them longer.

## 5. Working Slice — What's Actually Running

Built and verified against the real 5-source corpus (not synthetic/hypothetical data):

- **`write_annotation.py`** — the citation-groundedness gate. Validates `source_id`, extracts and normalizes the source PDF text, checks the quote matches verbatim, and only then writes an answer file with a References section.
- **`evaluator.py`** — the cross-model check. Calls a second model (`EVALUATOR_MODEL`, distinct from the generator) to judge whether a quote genuinely answers the question; returns ACCEPT or REJECT-with-reason.

Both are runnable standalone right now (`python3 write_annotation.py`, `python3 evaluator.py`), each with a real smoke test built in.

**Real output, this run:**

```
write_annotation — real quote, ACCEPT and save:
{'ok': True, 'path': '.../answers/answer_8b4cb2b1a3.md'}

write_annotation — bad source_id, REJECT:
{'ok': False, 'error': "Unknown source_id: 'not_a_real_id' not found in sources.json"}

write_annotation — paraphrase (not verbatim), REJECT:
{'ok': False, 'error': 'Quote not found verbatim in source (after normalization). Not saved.'}

write_annotation — quote crossing a hyphenated line break, ACCEPT:
{'ok': True, 'path': '.../answers/answer_167e7199d8.md'}

evaluator — real, on-topic quote:
{'ok': True}

evaluator — real quote, but off-topic (adversarial test):
{'ok': False, 'reason': 'The quote provides information about author details and does
 not mention accuracy or medical benchmarks.'}
```

**Not yet wired:** the full agent loop (`agent.py`) that lets the model choose tools autonomously. The remaining three tools (`list_sources`, `search_sources`, `read_source`, `lookup_citation`) are already built and unit-tested individually (see below); connecting all five into one autonomous loop is the next step, deliberately sequenced after the two integrity-critical components were verified first (Section 4).

## 6. Early Evaluation Evidence

Against the 13-case evaluation plan (PROPOSAL.md Section 4), 7 cases are runnable today without the full loop and have been executed against real data:

| Case | What it tests | Result |
|---|---|---|
| 1 (write_annotation half) | Real quote, correct citation | PASS |
| 5 | Real-but-off-topic quote, evaluator should reject | PASS |
| 6 | Bad source_id | PASS |
| 7 | Paraphrase, not verbatim | PASS |
| 8 | Source missing from sources.json | PASS |
| 9 | search_sources → read_source combo | PASS |
| 13 | Quote crossing a hyphenated line break | PASS (after a real fix) |

**Two real bugs found and fixed during this testing, not hypothetical:**

1. **Ligature characters.** Two of the five source PDFs (Liu2026, Xi2025) store letter pairs like "fi" and "fl" as single typographic ligature glyphs, not plain ASCII. A normally-typed quote containing "efficiency" silently failed to match until the normalizer was taught to expand these first.
2. **Hyphen-before-linebreak.** One source (AbouAli2025) breaks words across lines with a *space before* the hyphen ("advance -\nment"), not just after it. The original normalizer only stripped whitespace after the hyphen, producing "advance ment" (two words) instead of "advancement" — silently failing Case 13 until fixed.

Remaining 6 cases (2, 3, 4, 10, 11, 12) require the full agent loop and are the next milestone.

## 7. Updated Risk & Observability Plan

**Risks (from the proposal, unchanged):**

- Hallucinated citations — mitigated by `write_annotation`'s normalized groundedness check and the evaluator-optimizer step.
- Grounded but wrong answer — mitigated by the evaluator for obvious cases, human review gate for subtler ones.
- Incomplete Zotero metadata — mitigated by `list_sources` flagging the gap directly.
- Token/cost blow-up — mitigated by snippet-first search design and a concrete efficiency ceiling (Case 11).
- Agent cannot write directly to the final bibliography document — no tool exposes that write access.
- Second live API dependency (the evaluator) — mitigated by one technical retry, then automatic reject.

**New, found during this checkpoint's testing:**

- **Silent PDF-extraction artifacts.** Ligatures and hyphen-spacing are two confirmed cases; there may be others (e.g. different justified-text hyphenation, non-breaking spaces) not yet triggered by the current 5-source corpus. Mitigation: the normalizer is unit-tested against real extracted text for every new source added, not just written and trusted.

**Observability plan:**

- `common.llm.chat()`'s built-in `STATS` counter (calls, tokens, cache hits) gives call/token visibility for free — this is what will back Case 11's efficiency ceiling once the full loop exists.
- Every `write_annotation` rejection returns a structured `{"ok": False, "error": "..."}` rather than failing silently — the same pattern used for evaluator rejections (`{"ok": False, "reason": "..."}`), so a failure is always visible to whatever calls these tools, human or agent.
- Planned once `agent.py` exists: a per-run trace log (turn number, tool called, arguments, result) so a failed or rejected run can be replayed and understood after the fact, not just reported as a final failure message.

## 8. Next Steps

1. Wire `list_sources`, `search_sources`, `read_source`, `lookup_citation` (already built and unit-tested individually) plus `write_annotation` and the evaluator into one autonomous loop (`agent.py`) with the turn cap and evaluator budget enforced.
2. Run the remaining 6 evaluation cases (2, 3, 4, 10, 11, 12) against the full loop.
3. Extend the corpus to the full 7 literature-review sources once the two web-based sources are saved as text files.

---

## Addendum (post-submission, before final delivery)

Sections 2, 3, and 5 above describe the design as it stood at submission, including `write_annotation` as a standalone fifth tool. Wiring the full loop (Next Step 1) surfaced a design flaw in that version: `write_annotation` was modeled as a tool the agent could freely choose to call or skip, when a real answer actually *requires* a verified quote — not a genuine choice, a structural precondition. Prompt instructions and code-level gates both tried to coerce the model toward calling it anyway, which is the wrong fix for a mismodeled requirement.

**Resolution:** `write_annotation` was removed as a standalone tool. Verification is now part of `finish` itself — `finish` carries its answer plus a `citations` list, and every citation is checked automatically (verbatim match, then the evaluator) the moment `finish` is submitted with a real claim. A rejected `finish` returns the exact failing quote/source_id/reason and the loop continues; it does not end. This also resolves the `answer_text`-reuse fragility from Section 2 for free, since all citations for a question now arrive in one call instead of being merged across several.

The four remaining tools (`list_sources`, `search_sources`, `read_source`, `lookup_citation`), the evaluator's cross-model requirement, and the human approval gate are unchanged.

**Citation verification is now locked in per-citation, not just per-attempt (a corrected trade-off).** After several real runs, a genuinely two-source question (the AbouAli2025 + Du2026 case) kept failing not because the design was wrong to remove `write_annotation` as a skippable tool, but because merging citation submission fully into one atomic `finish` call had an un-intended side effect: bundling multiple citations meant one bad or network-unlucky citation forced the *whole* attempt to be redone, including citations that were already correct — a real regression from the old per-citation `write_annotation`, which locked each citation in independently the moment it passed. This was two separable design questions (should verification be skippable? should it be incremental or batched?) that got conflated into one merge. Fixed by keeping `finish` as the sole, still-automatic, still-non-skippable exit, but adding two in-memory sets to `_check_citations` — `verified_citations` (a citation that passes is locked in permanently for the run and never re-verified again, even if resubmitted next to a still-broken one) and `rejected_citations` (an unchanged resubmission of a real rejection is caught instantly without spending another evaluator call). Verified directly: a scripted two-citation run where one citation passes and one fails shows the passing citation is evaluated exactly once total across both the failed and the corrected attempt — confirming the network-timeout and re-verification cost that caused the real failures no longer recurs for citations already proven good. All 9 scripted test paths (the prior 8 plus this lock-in check) pass.

**Turn cap is now dynamic, not a flat 8.** Real runs surfaced two more issues after the finish/citations redesign above: (1) a genuinely two-source question (Case 3) found correct evidence in both sources but ran out of turns one short of finishing, because 8 turns assumed single-source difficulty; (2) evaluator network timeouts were being counted against the same 2-rejection budget as genuine content rejections, so a flaky API call could burn through the budget on an otherwise-correct answer (also seen in a real run). Both fixed: the turn cap is now `8 + 4 × (extra distinct sources touched)`, capped at 20 total, computed from sources actually engaged via `read_source` or a `finish` citation — a single-source question still gets exactly 8. And evaluator technical failures (network/timeout, exhausted their own internal retry) are now tagged `technical_error: true` and excluded from the 2-rejection budget, unless the same `finish` attempt also contains a real content-based rejection alongside it, in which case the content rejection still counts. All 8 scripted test paths (the original 6 plus 2 new ones covering pure-technical and mixed technical+content errors) pass. This redesign was reviewed against two independent LLMs before implementation and confirmed against 6 scripted test paths (happy path, single-citation rejection-then-correction, direct refusal with no citations, a real claim submitted with zero citations, repeated rejection to budget exhaustion, and turn-limit-reached) before being adopted.

**Observability plan (Section 7) is now implemented, not just planned.** Every call to `answer_question()` writes one JSON file to `capstone/logs/` (named by timestamp + question hash, so runs never overwrite each other) containing: the question, final answer, outcome (`success` / `rejected` per attempt / `budget_exhausted` / `turn_limit` / `insufficient_context_direct`), turns used, eval-rejections used, a per-run `usage` snapshot (`calls`, `tokens`, `cache_hits` — computed as the delta of `common.llm.STATS` before and after the run, so it reflects only this question, not the process-wide cumulative count), and a step-by-step `trace` (turn number, tool called, arguments, and result — truncated past 800 characters per field so a long `read_source` dump can't blow up the file). A rejected or failed run can be replayed and understood from this file alone, without needing to reproduce it live. Log files measured 0.5–1.8 KB each in testing — small enough to keep in the repo or attach to the write-up directly.

**Observability plan (Section 7), now implemented:** every call to `answer_question()` writes a per-run trace log to `capstone/logs/` — one JSON file per run, named by timestamp + a hash of the question + a random suffix (so repeated or concurrent runs of the same question never overwrite each other's record). Each file records the question, the final answer, a machine-readable outcome (`success` / `insufficient_context_direct` / `budget_exhausted` / `turn_limit`), how many turns and rejections were used, and a step-by-step trace: for every tool call, its arguments and result; for every `finish` attempt, whether it was accepted or rejected and the exact reason. Long text fields (e.g. `read_source`'s full-page output) are truncated in the log to keep files reviewable by a human. This directly satisfies the "replay a failed or rejected run" goal stated in Section 7 — it was designed but not built at submission time; it is built now, confirmed by re-running the same 6 scripted test paths above and inspecting the resulting log files.

## Addendum 2 — claim-level `finish` (composite answers no longer merged into one blob)

Real Case 3 runs kept failing for a reason distinct from the per-citation lock-in fix above: `finish` still carried one flat `answer_text` string backed by a flat `citations` list. For a genuinely two-source question, that meant the two sources' evidence had to be blended into a single piece of prose before submission — so a partially-grounded composite claim could, in principle, read as fully grounded even if only one of its two supporting citations actually passed verification. This was flagged as a real ambiguity risk, not just an efficiency one.

**Resolution:** `finish` now takes `"claims": [{"source_id", "quote", "statement"}, ...]` instead of `"answer"` + `"citations"`. Each claim is independently verified (verbatim match, then evaluator) and, if it passes, permanently locked into the run — never re-verified, never dependent on any other claim's fate. The final answer file gives each accepted claim its own section, tied only to its own source's in-text citation, so a composite answer is never glued into one paragraph that could misattribute or over-claim. A `finish` call can be repeated with only the new or still-failing claims; calling it with no new claims once at least one claim is locked in is now the model's own signal that it's satisfied and wants to stop.

**New byproduct: graceful partial success.** Because accepted claims no longer depend on siblings for coherence, a run that hits the turn cap or the rejection budget with at least one claim already locked in now finalizes with what it has (outcome `success_partial_turn_limit` / `success_partial_budget_exhausted`) instead of discarding everything and returning `INSUFFICIENT CONTEXT`. A run with zero locked-in claims still fails clean, as before.

`evaluator.py` is unchanged — each claim's own `statement` is passed in place of the original question, so the evaluator judges the narrower, per-claim assertion rather than the whole (possibly compound) question.

Verified with 11 scripted test paths covering: multi-claim happy path, partial rejection + correction with the good claim never re-verified, wrap-up-early via an empty `finish` call, graceful partial finalize at budget exhaustion, graceful partial finalize at turn limit, direct `INSUFFICIENT CONTEXT` with nothing accepted, and identical-rejected-claim resubmission not burning a second evaluator call. Also verified `tools.finalize_answer` directly against the real (placeholder-metadata) `sources.json` fixture: per-claim sections, a "Not Included" section for rejected claims, a References section built only from accepted sources, and clean `{"ok": False, ...}` returns for an empty claim list or an unknown `source_id`.

## Addendum 3 — a technical finish failure still silently cost a turn (real repro, fixed)

A real run of Case 1 against the live evaluator (`EVALUATOR_MODEL`) found the correct quote and submitted it on the very last available turn (turn 8 of 8, single source). `verify_quote` passed; the evaluator call then hit a network timeout ("OU LiteLLM Sandbox unreachable... timed out"), correctly tagged `technical_error: true` and correctly excluded from `MAX_EVAL_REJECTIONS`. But the run still failed with `INSUFFICIENT CONTEXT (turn limit reached without finishing)` — because the turn cap comparison was against the raw step counter, and a technical failure still advanced that counter like any other turn. This is the same two-axes mistake already fixed once for the rejection budget (Addendum, "Citation verification is now locked in per-citation"), recurring on the turn budget instead: an infrastructure hiccup outside the model's control shouldn't be able to consume the model's last chance to answer correctly.

**Resolution:** the turn cap is now checked against a separate `turns_used` counter, not the raw step count. A purely-technical `finish` failure draws from a small, separately-capped pool (`MAX_TECHNICAL_FINISH_RETRIES = 3`, tracked per-run) of free retries that do not advance `turns_used` — so a network blip doesn't cost a turn. Once that pool is exhausted, further technical failures are charged normally (both a turn and, if genuinely content-related, a rejection), which keeps a permanently-down evaluator from stalling the run forever; an absolute step-count backstop (`cap + MAX_TECHNICAL_FINISH_RETRIES + 2`) also guards against runaway loops as defense in depth.

Verified with 3 additional scripted test paths (14 total): a technical timeout on the last available turn, followed by a successful retry, still finalizes correctly (this is the direct repro of the real failure above); a permanently-failing evaluator still terminates the run (`turn_limit`, never fabricates an answer) instead of looping; and the free-retry pool size matches the constant.
