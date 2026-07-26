# Capstone Proposal — Literature Review Assistant with Citations

## 1. Scoped Use Case
I provide the agent with a folder of source documents plus a "sources.json" file exported from Zotero, including reference metadata.

**Does:** The agent answers a specific question about them, including a citation and a supporting quote. Each answer is written to a separate file, with a References section.  

**Does not:** The agent does not search the web or discover new sources, decide which sources belong in the set (I choose that up front). It also does not handle scanned or image-only PDFs.  

## 2. Architecture
**Setup (human, before the loop runs):** I select the source documents and export their bibliographic metadata from Zotero as CSL-JSON into "sources.json."  

**The loop:** Given a question, the agent picks one tool at a time and decides its own sequence — `list_sources`, `search_sources`, `read_source`, and `lookup_citation` are genuine, independent choices with no fixed order. It stops when it finishes or hits the turn cap (8 turns).  

**Verification lives in `finish`, not in a separate tool:** Earlier drafts had a fifth tool, `write_annotation`, that the agent was expected to remember to call before finishing. That put a structural requirement ("a real answer needs a verified quote") inside a tool menu of otherwise-genuine choices, which is the wrong model for it — verification isn't something the agent should be free to skip, any more than a database commit is free to skip its constraint checks. So `finish` now carries its own evidence, as a list of independent claims: `{"tool": "finish", "claims": [{"source_id", "quote", "statement"}, ...]}`. Submitting a real answer with no claims (and no `answer: "INSUFFICIENT CONTEXT"`) is rejected immediately.  

**Claim-level, not answer-level.** Each `{source_id, quote, statement}` is checked and locked in independently — never merged into one flowing paragraph. This matters for composite (multi-source) answers specifically: if the answer text were one blended block of prose, a claim that failed verification could still leave its influence baked into the wording of the parts that passed, silently making a partially-grounded answer read as fully grounded. Keeping each claim's `statement` standalone, tied only to its own citation in the final file, removes that ambiguity structurally rather than relying on the model to word things carefully. `finish` can be called more than once — only new or still-failing claims need resubmission, and calling it with an empty claims list once something is already locked in is the model's way of saying "stop here, I'm satisfied."  

**Evaluator-optimizer check:** The moment `finish` is submitted with claims, each one is checked automatically in two steps: first a deterministic check that the quote appears verbatim in the named source, then a call to a second model that judges whether the quote genuinely supports that claim's own `statement`. That second model goes to a **different model family** than the generator, picked through an `EVALUATOR_MODEL` environment variable (same pattern as `COURSE_MODEL` in Build Challenge 2), so the evaluator does not share the generator's blind spots. A claim that fails is reported back with its reason; a claim that passes is locked in permanently and never re-verified, even if resubmitted alongside a still-failing sibling.

**Turn budget rule:** The main loop's turn cap scales with how many distinct sources the run actually touches (via `read_source` or a `finish` citation) — 8 turns base, +4 for each additional source beyond the first, capped at 20 total. A single-source question still gets exactly 8, unchanged; a two-source question gets 12. This was revised from a flat 8-turn cap after a real run (Case 3, a genuinely two-source question) hit the 8-turn ceiling one turn short of finishing despite finding the correct evidence in both sources — evidence that a flat cap conflated "how hard is this question" with "how many sources does it need," when those aren't the same thing. Rejected `finish` attempts have their own separate budget: up to 2 rejections total (not per-citation — one attempt with several bad citations still only costs 1). A network or timeout failure inside the evaluator call gets one technical retry inside `evaluate()` itself; if that's also exhausted, the resulting failure is marked as technical and does NOT consume the 2-rejection budget (only a turn) — unless the same `finish` attempt also contains a genuine content-based rejection, which still counts normally. If either the (now dynamic) turn cap or the 2-rejection budget is hit first, the run stops: nothing is saved, and the failure is reported with its last reason.

**One question, one answer file rule:** The user expects exactly one output file per question, always — never split across several files, even when the answer draws on facts from multiple sources. Because all citations for a question now arrive together in a single successful `finish` call, this is structural rather than a rule the model has to remember: `finalize_answer` writes one file from the full citation list in one shot. (Earlier, with citations submitted one `write_annotation` call at a time, this depended on the model reusing an identical `answer_text` string across calls — a fragile convention that this redesign removes rather than just documents.)

**Where control lives:** The model decides which information-gathering tool to call and when, and how many times. That's the judgment this task needs and the reason this is an agent rather than a fixed workflow. What's hard-coded is the turn cap, the rejection budget, the fact that a real answer requires verified citations, and the fact that the agent has no tool capable of writing to the final bibliography document — none of these constrain *how* the agent gathers evidence, only what counts as a valid way to conclude.

**Human approval gate:** After the loop finishes, I open the draft answer file to confirm both that the quotes actually support the claim and that the citations are correct.

**Deferred for future work (not implemented under this deadline):** an optional, side-effect-free `validate_quote` tool the agent could call *during* exploration to pre-check a candidate quote before committing to `finish`, which would reduce wasted rejection cycles without reintroducing a skippable-but-required tool (skipping it would only cost efficiency, not correctness).

## 3. Tools
**list_sources():** Reads the source folder and cross-references "sources.json" internally, then returns each file's name together with its source_id (for example: `{"file": "xi2025.pdf", "id": "Xi2025LLMAgents"}`). If a file has no matching entry in "sources.json," it is still listed, with its id marked as missing, so the agent can report the gap instead of guessing. This one tool call gives the agent both pieces of information it needs — no extra tool or turn required.

**search_sources(query):** Searches all source documents and returns matching passages paired with filenames (snippets, not full documents). Same design as "search_notes_snippet" from Build Challenge 1, to keep token costs down. Two stages: the query is tried as one exact phrase, and only if nothing contains it is it retried as separate words, returning passages containing all of them (reported via `match_mode`). The second stage exists because a caller asking about several things at once writes a multi-concept query and expects keyword behaviour, while a bare substring search silently answers a different question. Matching ignores whitespace and hyphens for the same reason verify_quote does (below), and spans up to three adjacent sentences, since prose and figure captions routinely split one fact across a sentence boundary. Every returned snippet is a real span of the source and passes verify_quote as-is.

**read_source(name):** Returns the opening window of one named document. Used when a snippet from "search_sources" is not enough context. A missing filename returns the list of available sources rather than a bare "not found", so an invented name self-corrects instead of costing turns.

**lookup_citation(source_id):** Looks up one source's author, year, title, and publisher from "sources.json" and returns two things for that single source only: the in-text citation form (e.g., "(Smith, 2023)") and that source's one reference-list entry. It never returns information about any other source. This keeps the agent from inventing citation details.

**Not a standalone tool — part of `finish`, and verified per-claim, not per-attempt.** Removing `write_annotation` as a standalone tool fixed the real problem (verification being skippable). An early version of `finish` then bundled everything into one flat `answer_text` + `citations` submission, which reintroduced two of the old design's problems in a new form: (1) a single bad or unlucky (e.g. a network timeout) citation forced the *entire* attempt to be redone, including citations already correct, and (2) a composite, multi-source answer had to be pre-blended into one paragraph before submission, so a claim that failed verification could still leave its wording baked into the parts that passed.

The current design fixes both by making `finish` claim-level: `_check_claims` checks each `{source_id, quote, statement}` against two permanent, in-memory sets for the run — `verified_keys` (locked in once ACCEPTed, never re-checked again even if resubmitted alongside a still-broken claim) and `rejected_keys` (an unchanged resubmission of a real rejection is caught instantly, without spending another evaluator call). `finish` is still the only exit and still requires every claim to pass through this same automatic check — nothing about "is verification skippable" changed.

Verification and saving are two internal functions invoked automatically when `finish` carries claims, not something the agent calls directly:

- `verify_quote(source_id, quote)` checks that "source_id" exists in "sources.json" and that "quote" appears in that source's text. Both sides are reduced to a canonical form first — ligatures expanded, curly quotes straightened, then all whitespace and hyphens removed — before an exact substring match. The words themselves, in order, must still be present; the match is never fuzzy. Whitespace is excluded because PDF extraction corrupts it in both directions (a space vanishing inside `wereﬁltered`, a space appearing inside `t hat`) and loses hyphens at line breaks. Those are artifacts of a lossy extraction, not properties of the document, and comparing on them inverted the check: a reader quoting what a sentence *says* was rejected while one reproducing the corruption was accepted. ~8% of quotable sentences in the corpus carry such a corruption, and it is not even stable across pypdf versions.

- `finalize_answer(accepted_claims, rejected_claims)` runs once the model signals it's done (either every submitted claim passed, or it called `finish` with no new claims after at least one was already locked in). It writes one answer file in a single call: one section per accepted claim (its own statement + quote, tied to its own citation), an optional "Not Included" section listing any rejected claims and why, and a References section built only from the accepted claims' sources.

## 4. Evaluation Plan
Thirteen test cases are listed below. Cases 3, 10, and 11 have concrete pass criteria decided in advance, so grading them does not require judgment calls at review time.

| # | Test case | Pass looks like |
|---|-----------|------------------|
| 1 | Simple factual question, one obvious source | Correct source cited, quote is real, citation + reference entry both correct |
| 2 | Same question, re-run once | A human reviewer confirms both runs cite the same source_id and report the same core fact from that source. Exact wording may differ. |
| 3 | Question answerable by two known relevant sources (chosen in advance) | The final answer's References section lists both of the pre-identified source_ids — checked directly, no judgment call needed |
| 4 | Question with no answer in any source | Agent says "not found," doesn't invent an answer |
| 5 | Question where a real quote exists but is off-topic | The evaluator-optimizer step catches it and the agent tries again |
| 6 | Bad or nonexistent source_id cited in a finish call | That claim is rejected with an error, nothing gets saved for it, agent gets a chance to retry |
| 7 | A paraphrased "quote" that is not literally in the source text | Rejected by verify_quote inside the finish check |
| 8 | Source missing from sources.json | Agent reports the gap instead of guessing author/year |
| 9 | Question needing a snippet search, then a full read for context | search_sources → read_source combo works as intended |
| 10 | Two similar quotes in the same source, with the better match decided in advance | Agent's chosen quote matches the one pre-identified as correct |
| 11 | Any typical single-source question | ≤8 model calls and ≤15,000 tokens — revised from an original ≤4,000-token guess after a real run measured 12,597 tokens for one question; the call ceiling held, the token estimate didn't account for a full-source `read_source` call persisting in conversation history across turns |
| 12 | Multi-source answer file | References section lists only the sources actually cited in that file |
| 13 | A genuine quote that crosses a line break in the source PDF | verify_quote's normalized match still accepts it (complements case 7, which tests the opposite failure) |

## 5. Risks
**Hallucinated citations:** the agent cites a source or quote that isn't real. Mitigated by `verify_quote`'s normalized groundedness check and the evaluator-optimizer step, both run automatically on every `finish` attempt with real claims.

**Grounded but wrong answer:** a real quote that still misreads the question. Mitigated by the evaluator check for obvious cases, and the human review gate for subtler ones.

**Incomplete Zotero metadata:** a source missing from sources.json. Mitigated by list_sources flagging the gap directly, instead of lookup_citation guessing.

**Better retrieval making the negative case harder (new, observed):** improving search made "no source answers this" *harder* to reach, not easier. When searches came back barren the absence was obvious; now a question about dollar cost surfaces genuine passages about computational cost, and the model submits them. Case 4 still passes, but only because the evaluator's relevance check rejects all of them. Retrieval creates the temptation and the evaluator catches it, and neither layer alone would suffice. Worth remembering before treating a recall improvement as a free win.

**Token/cost blow-up:** more tool calls than needed, the same surprise found in the Build Challenge 1 redesign. Mitigated by snippet-first search design and a concrete efficiency ceiling (case 11).

**Agent cannot write directly to the final document:** if it bypassed review, it could push an unverified answer straight into the graded bibliography. Mitigated architecturally: no tool exposes write access to that file, only to draft files.

**Second live API dependency (new):** the evaluator's cross-model call adds a second point of failure beyond the generator. Mitigated by retries and then a fail-safe reject: never save an unvalidated answer. Real runs showed the harder half of this risk is not the failure itself but *misreporting* it — an unreachable evaluator let a run report `INSUFFICIENT CONTEXT` on a question it had already answered correctly, and a reply cut off mid-sentence was recorded as a content rejection because it began with `REJECT`. An outage presented as an evidentiary finding is worse than an outage, so unreachable, empty, truncated, and unparseable responses are now all distinguished from real verdicts, and a circuit breaker ends the run saying `EVALUATOR UNAVAILABLE ... NOT a finding that the sources lack an answer`.

**A model that keeps submitting bad single-claim finish attempts instead of using the exploration tools:** since a rejected `finish` costs one of only 2 rejection-budget slots, a model that doesn't take the hint from the returned error could burn its budget quickly without ever calling `search_sources`/`read_source` again. Mitigated by the (now dynamic) turn cap as a hard backstop either way, and by echoing back the exact failing quote/source_id/reason so the retry has enough information to actually change strategy.

**Resolved by this iteration (previously listed as a risk):** *one question split into multiple answer files.* Earlier this depended on the model reusing an identical `answer_text` string across several `write_annotation` calls — a fragile convention. Now `finalize_answer` runs once per completed run, over the full set of accumulated accepted claims, so it always writes exactly one file. There is no multi-call state for the model to get wrong.

**Also resolved by this iteration:** *a composite answer misrepresenting partially-grounded content as fully grounded.* Because claims are recorded and finalized individually rather than blended into one paragraph, a claim that never passes verification simply never appears in the output. So, it cannot leave a trace in the wording of the claims that did pass.

## 6. Work Plan
- 07/24/2026 - 07/26/2026, is the review capstone & Checking all test cases.
- 07/27/2026 - 07/31/2026, finalizing the agent.
- 08/03/2026 - 08/05/2026, Capstone studio.

I ask questions when the tool takes a long time to complete its task (latency issue), when the evaluator-optimizer stage is not working properly (accepting incorrect answers or rejecting correct ones), or when the agent seems to be consuming a lot of tokens.