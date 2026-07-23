# Proposal Revision Summary

| # | Issue | Solution | Reason |
|---|-------|----------|--------|
| 1 | Turn budget: a clean run already uses 4-5 of 8 turns; evaluator rejections eat the same budget | Main loop keeps its 8-turn cap. Evaluator gets its own separate budget of 2 content rejections, plus 1 technical retry on API failure. Either cap hit first stops the run: nothing saved, failure reported with reason | Keeps the original guardrail (turn cap) intact instead of arbitrarily raising it, and separates "technical failure" from "content quality" so each is handled by the pattern that fits it |
| 2 | write_annotation's literal quote match rejects honest quotes broken by PDF line breaks, hyphenation, or curly quotes | Normalize both sides (collapse whitespace, straighten quotes, rejoin hyphenated line-breaks) before comparing. Match stays exact, never fuzzy. Added test case 13: a true quote crossing a line break, should pass | Fixes the real extraction artifact without weakening the groundedness guarantee — fuzzy matching was rejected because it could let a paraphrase slip through |
| 3 | Case 2 (re-run consistency) demanded an identical string, which fails against a non-deterministic model | Pass rule: a human reviewer confirms both runs cite the same source_id and report the same core fact. Wording can differ | Mirrors the Mini-Build 0 approach of treating model variation as data, not failure |
| 4 | list_sources returns filenames, but lookup_citation and write_annotation need source_id — no defined mapping | list_sources reads the folder and sources.json together internally, returning file+id pairs in one call. Missing metadata is flagged, not hidden | Closes the gap with zero new tools and zero new turns; source_id still comes only from verified Zotero data, never guessed |
| 5 | Capstone had no live-service component after the scope-advice reversal | Evaluator-optimizer now calls a different-model-family LLM via an EVALUATOR_MODEL environment variable (same pattern as COURSE_MODEL in BC2) | Directly fixes an already-known weakness (evaluator sharing the generator's blind spots) instead of adding an unrelated live service like web search, which would undercut the human-curated-source design |
| 6 | Case 11 (efficiency) had no concrete pass number | Set ≤8 model calls and ≤4,000 tokens for a typical single-source question | Derived from the loop's own turn cap and measured costs in BC1/BC2, not an arbitrary figure |
| 7 | Cases 3 and 10 had vague pass criteria ("didn't miss the source," "picked the better quote") | Both test questions are designed in advance with a known correct answer: case 3's two relevant source_ids, case 10's better-matching quote. Pass = matches the pre-decided answer | Moves the judgment call to test-design time, where it's a one-time decision, instead of leaving it open at every review |
| 8 | lookup_citation's return was ambiguous — one citation, or the whole reference list? | Returns exactly two things for one source only: its in-text form and its single reference-list entry. write_annotation aggregates entries across calls into each file's References section | Matches what was already said about write_annotation building the References section, and removes the ambiguity without changing the design |



1. Issue: Evaluator rejections use the main 8-turn budget.
    - Solution: Evaluator gets its own separate budget: 2 content rejections plus 1 technical retry.
    - Reason: Keeps the turn cap intact and separates technical failure from content quality.

2. Issue: Literal quote match rejects honest quotes broken by line breaks or curly quotes.
    - Solution: Normalize whitespace, quotes, and hyphenation before an exact match. Added test case 13.
    - Reason: Fixes a real extraction text without allowing paraphrased matches.

3. Issue: Case 2 required an identical string match.
    - Solution: Human reviewer confirms both runs cite the same source and same core fact (wording can differ).
    - Reason: Treats model variation as data, not failure(the same as the Mini-Build 0 approach).

4. Issue: No defined mapping between filenames (from list_sources) and source_ids.
    - Solution: list_sources reads the folder and sources.json together, returning file-and-id pairs.
    - Reason: Closes the gap with no new tools or turns. Also, source_id still comes only from verified data.

5. Issue: The capstone had no live-service component.
    - Solution: Evaluator-optimizer calls a different model LLM via an EVALUATOR_MODEL variable.
    
6. Issue: Case 11 (efficiency) had no acceptance criteria.
    - Solution: Set a ceiling of 8 model calls and 4,000 tokens per question.
    - Reason: Based on the loop's turn cap and estimated costs from previous build challenges.

7. Issue: Cases 3 and 10 had no clear pass criteria.
    - Solution: Both test questions are designed in advance with a known correct answer: case 3's two relevant source_ids, case 10's better-matching quote.
    - Reason: Moves the judgment call to test-design time because it's a one-time decision. There is no need to remain open at review.

8. Issue: lookup_citation's return one citation, or the whole reference list?
    - Solution: Returns exactly two fields for one source only: in-text form and its reference entry.
    - Reason: Matches how write_annotation already builds the References section, and removes the ambiguity without changing the design.