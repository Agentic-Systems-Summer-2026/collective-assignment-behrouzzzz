# Capstone Design Review & Progress Checkpoint — Literature Review Assistant with Citations

## 1. Scoped Use Case

I provide the agent with a folder of source documents plus a `sources.json` file exported from Zotero, including reference metadata.

**Does:** The agent answers a specific question about them, including a citation and a supporting quote. Each answer is written to a separate file, with a References section.

**Does not:** The agent does not search the web or discover new sources, decide which sources belong in the set (I choose that up front). It also does not handle scanned or image-only PDFs.


## 2. Architecture

**Setup (human, before the loop runs):** I select the source documents and export their bibliographic metadata from Zotero as CSL-JSON into `sources.json`.

**The loop:** Given a question, the agent picks one tool at a time and decides its own sequence out of five tools (Section 3). It stops when it has an answer or hits the turn cap (8 turns).

**Evaluator-optimizer check:** Before the agent is allowed to save an answer, a separate model call checks whether the proposed quote actually answers the question. This call goes to a different model than the generator, picked through an `EVALUATOR_MODEL` variable. So, the evaluator does not share the generator's blind spots. If the evaluator rejects the answer, the reason is fed back into the loop as another turn.

**Turn budget rule:** The main loop keeps its 8-turn cap. The evaluator has its own separate budget: up to 2 content-based rejections. A network or timeout failure when calling the evaluator gets one technical retry, tracked separately from the 2 content rejections (mirrors the retry pattern from Build Challenge 3). If either cap is hit first, the run stops: nothing is saved, and the failure is reported with its last reason.

**Where control lives:** The model decides which tool to call and when. This is judgment and the reason this is an agent rather than a fixed workflow. But several things are hard-coded, not left to the model: the turn cap, the evaluator's separate retry budget, and the fact that the agent has no tool capable of writing directly to the final bibliography document.

**Human approval gate:** After the loop finishes, I open the draft annotation file to confirm both that the quote actually supports the claim and that the citation is correct.


## 3. Tools

**list_sources():** Reads the source folder and cross-references "sources.json" internally. Then returns each file's name and its source_id in a dictionary format (for example: `{"file": "abc.pdf", "id": "a1b2c3"}`). If a file has no matching entry in "sources.json," it is still listed and its id marked as null. So, the agent can report the gap instead of guessing. This tool gives the agent both pieces of information it needs.

**search_sources(query):** Searches all source documents and returns matching lines paired with filenames (snippets, not full documents). Same design as "search_notes_snippet" from Build Challenge 1 to keep token costs down.

**read_source(name):** Returns the full text of one named document. Used when a snippet from "search_sources" is not enough context.

**lookup_citation(source_id):** Looks up one source's author, year, title, and publisher from "sources.json" and returns two things for that single source only: the in-text citation form (e.g., "(Smith, 2023)") and that source's one reference-list entry. It never returns information about any other source. It could help to prevent the agent from inventing citation details.

**write_annotation(source_id, quote, answer_text):** Before saving, it checks that "source_id" exists in "sources.json," and that "quote" appears in that source's text. Both sides of this comparison are normalized first (extra whitespace collapsed, curly quotes converted to straight quotes, and line-break hyphens rejoined). So, a real quote that happens to cross a line break in the PDF still passes. If either check fails, the tool returns an error instead of writing. On success, it saves the answer to its own file with a References section built from whichever "lookup_citation" entries were used for that answer.


## 4. Design Rationale — Trade-offs Considered and Defended

**Turn budget for the evaluator.** 
- Considered: Raise the main 8-turn cap to absorb evaluator retries, vs. give the evaluator its own separate budget. 
- Chose: Separate budget (2 content rejections + 1 technical retry, tracked apart from the 8-turn cap). 
- Why: Raising the shared cap would let a flaky evaluator silently eat into the generator's budget; keeping them separate means a technical failure and a content disagreement are diagnosed differently, and the original turn-cap guardrail from earlier build challenges stays intact instead of being loosened.

**Quote matching strictness.** 
- Considered: Fuzzy/Semantic matching for quotes (to survive PDF extraction noise) vs. strict exact-match after normalization. 
- Chose: Exact match, but normalize whitespace, curly quotes, ligatures, and hyphenated line breaks first. 
- Why: Fuzzy matching could let a paraphrase slip through. So, as a result, defeats the entire point of a citation-accuracy tool. Two real extraction bugs (connected characters, hyphen-before-linebreak) were found and fixed this way, without ever loosening the match itself.

**Second live API dependency (the evaluator).** 
- Considered: Skip a second live service and keep everything local/file-based, vs. add one. 
- Chose: Add exactly one — the cross-model evaluator — rather than bolting on an unrelated service like web search. 
- Why: This directly fixes an already-known weakness (an evaluator sharing the generator's blind spots) instead of adding risk for its own sake; adding live web search, by contrast, would undercut the human-curated-source-set trust model that is central to this project's citation-accuracy story.

**Which two components to build and verify first.** 
- Considered: Build breadth-first (a thin version of all 5 tools) vs. depth-first on the two components identified as highest-risk in review feedback (`write_annotation`'s groundedness check, and the evaluator-optimizer). 
- Chose: Depth-first on those two. 
- Why: These two are the actual integrity guarantees of the system. Verifying these two against real data first, before wiring the full loop, is what actually stands out the two extraction bugs, while building all five shallowly first would likely have hidden them longer.


## 5. Working Slice — What's Actually Running

Built and verified against the 5 test cases:

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

**Not yet completed** The full agent loop (`agent.py`) that lets the model choose tools autonomously. The remaining three tools (`list_sources`, `search_sources`, `read_source`, `lookup_citation`) also need to be built. Then, the next step is to connect all five into one autonomous loop.


## 6. Early Evaluation Evidence

7 evaluation cases are runnable today without the full loop and have been executed with real data:

| Case | What it tests | Result |
|---|---|---|
| 1 (write_annotation half) | Real quote, correct citation | PASS |
| 5 | Real-but-off-topic quote, evaluator should reject | PASS |
| 6 | Bad source_id | PASS |
| 7 | Paraphrase, not verbatim | PASS |
| 8 | Source missing from sources.json | PASS |
| 9 | search_sources → read_source combo | PASS |
| 13 | Quote crossing a hyphenated line break | PASS (after a real fix) |


### Two real bugs found and fixed during this testing, not hypothetical:

1. **connected characters.** Two of the five source PDFs (Liu2026, Xi2025) store letter pairs like "fi" and "fl" as single character. A normally-typed quote containing "efficiency" silently failed to match until the normalizer was taught to expand these first.
2. **Hyphen-before-linebreak.** One source (AbouAli2025) breaks words across lines with a space before the hyphen ("advance -\nment"), not just after it. The first version normalizer only stripped whitespace after the hyphen, producing "advance ment" (two words) instead of "advancement," which resulted in silently failing test case 13.

**!!!** Remaining 6 cases (2, 3, 4, 10, 11, 12) require the full agent loop and are the next milestone.


## 7. Updated Risk & Observability Plan

### Risks

- **Hallucinated citations** —> mitigated by `write_annotation`'s normalized groundedness check and the evaluator-optimizer step.
- **Grounded but wrong answer** —> mitigated by the evaluator for obvious cases, human review gate for subtler ones.
- **Incomplete Zotero metadata** —> mitigated by `list_sources` flagging the gap directly.
- **Token/cost blow-up** —> mitigated by snippet-first search design and a concrete efficiency ceiling (Case 11).
- **Agent cannot write directly to the final bibliography document** —> no tool exposes that write access.
- **Second live API dependency (the evaluator)** —> mitigated by one technical retry, then automatic reject.

### New, found during this checkpoint's testing

**Silent PDF-extraction artifacts.** 
- Connected letters and hyphen-spacing are two confirmed cases; there may be others (e.g. different justified-text hyphenation, non-breaking spaces) not yet triggered by the current 5-source corpus. 
- Mitigation: the normalizer is unit-tested against real extracted text for every new source added, not just written and trusted.

**Observability plan:**
- `common.llm.chat()`'s built-in `STATS` counter (calls, tokens, cache hits) gives call/token visibility for free — this is what will back Case 11's efficiency ceiling once the full loop exists.
- Every `write_annotation` rejection returns a structured `{"ok": False, "error": "..."}` rather than failing silently — the same pattern used for evaluator rejections (`{"ok": False, "reason": "..."}`), so a failure is always visible to whatever calls these tools, human or agent.
- Planned once `agent.py` exists: a per-run trace log (turn number, tool called, arguments, result) so a failed or rejected run can be replayed and understood after the fact, not just reported as a final failure message.


## 8. Next Steps

1. Wire `list_sources`, `search_sources`, `read_source`, `lookup_citation` and connect all tools and evaluator to one autonomous loop (`agent.py`). The agent has the turn cap and evaluator budget enforced.
2. Run all evaluation cases against the full loop.
