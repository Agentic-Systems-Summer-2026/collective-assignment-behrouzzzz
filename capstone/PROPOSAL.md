# Capstone Proposal — Literature Review Assistant with Citations

## 1. Scoped Use Case
I provide the agent with a folder of source documents plus a "sources.json" file exported from Zotero, including reference metadata.
**Does:** The agent answers a specific question about them, including a citation and a supporting quote. Each answer is written to a separate file, with a References section.  
**Does not:** The agent does not search the web or discover new sources, decide which sources belong in the set (I choose that up front). It also does not handle scanned or image-only PDFs.  

## 2. Architecture
**Setup (human, before the loop runs):** I select the source documents and export their bibliographic metadata from Zotero as CSL-JSON into "sources.json."  
**The loop:** Given a question, the agent picks one tool at a time and decides its own sequence. It stops when it has an answer or hits the turn cap (8 turns).  
**Evaluator-optimizer check:** Before the agent is allowed to save an answer, the code runs one extra model call that checks whether the proposed quote actually answers the question. This call goes to a different model family than the generator.It is picked through an `EVALUATOR_MODEL` environment variable. So, the evaluator does not share the generator's blind spots. If the evaluator rejects the answer, the reason is fed back into the loop as another turn.  
**Turn budget rule:** The main loop keeps its 8-turn cap. The evaluator has its own separate budget: up to 2 rejections. A network or timeout failure when calling the evaluator gets one technical retry, tracked separately from the 2 content rejections. If either the 8-turn cap or the 2-rejection budget is hit first, the run stops. Then, nothing is saved, and the failure is reported with its last reason.  
**Where control lives:** The model decides which tool to call and when. That's the judgment this task needs and the reason this is an agent rather than a fixed workflow. But several things are hard-coded, not left to the model: the turn cap, the evaluator's separate retry budget, and the fact that the agent has no tool capable of writing to the final bibliography document.  
**Human approval gate:** After the loop finishes, I open the draft annotation file to confirm both that the quote actually supports the claim and that the citation is correct.

## 3. Tools
**list_sources():** Reads the source folder and cross-references "sources.json" internally. Then returns each file's name and its source_id in a dictionary format (for example: `{"file": "abc.pdf", "id": "a1b2c3"}`). If a file has no matching entry in "sources.json," it is still listed and its id marked as null. So, the agent can report the gap instead of guessing. This tool gives the agent both pieces of information it needs.
**search_sources(query):** Searches all source documents and returns matching lines paired with filenames (snippets, not full documents). Same design as "search_notes_snippet" from Build Challenge 1 to keep token costs down.
**read_source(name):** Returns the full text of one named document. Used when a snippet from "search_sources" is not enough context.
**lookup_citation(source_id):** Looks up one source's author, year, title, and publisher from "sources.json" and returns two things for that single source only: the in-text citation form (e.g., "(Smith, 2023)") and that source's one reference-list entry. It never returns information about any other source. It could help to prevent the agent from inventing citation details.
**write_annotation(source_id, quote, answer_text):** Before saving, it checks that "source_id" exists in "sources.json," and that "quote" appears in that source's text. Both sides of this comparison are normalized first (extra whitespace collapsed, curly quotes converted to straight quotes, and line-break hyphens rejoined). So, a real quote that happens to cross a line break in the PDF still passes. If either check fails, the tool returns an error instead of writing. On success, it saves the answer to its own file with a References section built from whichever "lookup_citation" entries were used for that answer.

## 4. Evaluation Plan
Thirteen test cases are listed below. Cases 3, 10, and 11 have concrete pass criteria decided in advance, so grading them does not require judgment calls at review time.

| # | Test case | Pass looks like |
|---|-----------|------------------|
| 1 | Simple factual question, one obvious source | Correct source cited, quote is real, citation + reference entry both correct |
| 2 | Same question, re-run once | A human reviewer confirms both runs cite the same source_id and report the same core fact from that source. Exact wording may differ. |
| 3 | Question answerable by two known relevant sources (chosen in advance) | The final answer's References section lists both of the pre-identified source_ids — checked directly, no judgment call needed |
| 4 | Question with no answer in any source | Agent says "not found," doesn't invent an answer |
| 5 | Question where a real quote exists but is off-topic | The evaluator-optimizer step catches it and the agent tries again |
| 6 | Bad or nonexistent source_id passed to write_annotation | Tool rejects it with an error, nothing gets saved |
| 7 | A paraphrased "quote" that is not literally in the source text | write_annotation rejects it |
| 8 | Source missing from sources.json | Agent reports the gap instead of guessing author/year |
| 9 | Question needing a snippet search, then a full read for context | search_sources → read_source combo works as intended |
| 10 | Two similar quotes in the same source, with the better match decided in advance | Agent's chosen quote matches the one pre-identified as correct |
| 11 | Any typical single-source question | ≤8 model calls and ≤4,000 tokens — a ceiling based on the turn cap and measured costs from Build Challenges 1 and 2, not a guess |
| 12 | Multi-source answer file | References section lists only the sources actually cited in that file |
| 13 | A genuine quote that crosses a line break in the source PDF | write_annotation's normalized match still accepts it (complements case 7, which tests the opposite failure) |

## 5. Risks
**Hallucinated citations:** the agent cites a source or quote that isn't real. Mitigated by write_annotation's normalized check and the evaluator-optimizer step.
**Grounded but wrong answer:** a real quote that still misreads the question. Mitigated by the evaluator check for obvious cases, and the human review gate for subtler ones.
**Incomplete Zotero metadata:** a source missing from sources.json. Mitigated by list_sources flagging the gap directly, instead of lookup_citation guessing.
**Token/cost blow-up:** more tool calls than needed, the same surprise found in the Build Challenge 1 redesign. Mitigated by snippet-first search design and a concrete efficiency ceiling (case 11).
**Agent cannot write directly to the final document:** Mitigated architecturally: no tool exposes write access to that file, only to draft files.
**Second live API dependency (new):** the evaluator's cross-model call adds a second point of failure beyond the generator. Mitigated by one technical retry, then an automatic reject (the same fail-safe rule as the turn cap: never save an invalidated answer).

## 6. Work Plan
Wednesday is dedicated to finishing architecture fixes as well as building tools with priority on write_annotation and the evaluator first. Thursday, Capstone Design Review as well as testing against the 13 evaluation cases.

I ask questions when the tool takes a long time to complete its task (latency issue), when the evaluator-optimizer stage is not working properly. Also when the agent seems to be consuming a lot of tokens.
