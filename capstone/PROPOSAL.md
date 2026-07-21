# Capstone Proposal — Literature Review Assistant with Citations

## 1. Scoped Use Case
I provide the agent with a folder of source documents plus a "sources.json" file exported from Zotero, including reference metadata.
**Does:** The agent answers a specific question about them, including a citation and a supporting quote. Each answer is written to a separate file, with a References section.  
**Does not:** The agent does not search the web or discover new sources, decide which sources belong in the set (I choose that up front). It also does not handle scanned or image-only PDFs.  

## 2. Architecture
**Setup (human, before the loop runs):** I select the source documents and export their bibliographic metadata from Zotero as CSL-JSON into "sources.json."  
**The loop:** Given a question, the agent picks one tool at a time and decides its own sequence. It stops when it has an answer or hits the maximum cap (8 turns).  
**Evaluator-optimizer check:** Before the agent is allowed to save an answer, the code runs one extra model call in which it checks whether the proposed quote actually answers the question. If not, the reason is fed back into the loop as another turn. The loop is still limited to the same turn cap.
**Where control lives:** The model decides which tool to call and when. That's the judgment this task needs and the reason this is an agent rather than a fixed workflow. But two things are hard-coded: the turn cap and the fact that the agent has no tool capable of writing to the final bibliography document.
**Human approval gate:** After the loop finishes, I open the draft annotation file to confirm both the quote actually supports the claim and the citation is correct.

## 3. Tools
**list_sources():** returns the filenames of every document in the source set. It is needed first, so the agent knows the available resources.
**search_sources(query):** searches all source documents and returns matching lines paired with filenames (snippets, not full documents). Same design as "search_notes_snippet" from Build Challenge 1 to keep token costs down.
**read_source(name):** returns the full text of one named document. It is supposed to be used when the "search_sources" do not return enough context.
**lookup_citation(source_id):** Looks up a source's author, year, title, and publisher from "sources.json" and returns both the citation and the full reference list. It could help to prevent the agent from inventing citation details.
**write_annotation(source_id, quote, answer_text):** First, it checks that "source_id" exists in "sources.json" and that "quote" literally appears in that source's text. It returns an error instead of writing if either check fails. Then, it saves the answer to a file with a References section. This is the tool supposed to mitigate the risk of hallucinated citations.

## 4. Evaluation Plan
Twelve test cases are listed below:

| # | Test case | Pass looks like |
|---|-----------|------------------|
| 1 | Simple factual question, one obvious source | Correct source cited, quote is real, cite + reference entry both correct |
| 2 | Same question, re-run once | Same source and same conclusion both times (consistency check) |
| 3 | Question answerable by more than one source | Agent doesn't miss the second relevant source |
| 4 | Question with no answer in any source | Agent says "not found," doesn't invent an answer |
| 5 | Question where a real quote exists but is off-topic | Evaluator-optimizer catches it and the agent tries again |
| 6 | Either bad or nonexistent "source_id" passed to "write_annotation" | Tool rejects it with an error, nothing gets saved |
| 7 | A paraphrased "quote" that isn't literally in the source text | "write_annotation" checks it and rejects it |
| 8 | Source missing from "sources.json" | Agent reports the gap instead of guessing author/year |
| 9 | Question needing a snippet search, then a full read for context | "search_sources" → "read_source" combo works as intended |
| 10 | Question with two similar quotes in the same source | Agent picks the one that best matches the question |
| 11 | Any typical question | Reasonable token/call count, efficiency finding |
| 12 | Multi-source answer file | References section lists only the sources actually cited in that file |

## 5. Risks
**Hallucinated citations:** the agent cites a source or quote that isn't real. Mitigated by "write_annotation"'s and the evaluator-optimizer step.
**Grounded but wrong answer:** a real quote that still misreads the question. Mitigated by the evaluator check for obvious cases, and the human review gate for subtler ones.
**Incomplete Zotero metadata:** a source missing from "sources.json". Mitigated by "lookup_citation".
**Token/cost blow-up:** more tool calls than needed, the same surprise found in the BC1 redesign. Try to mitigate it by snippet-first search design.
**Agent cannot write directly to the final document:** Mitigated architecturally: no tool exposes write access to that file, only to draft files.

## 6. Work Plan
Monday, submit this proposal for scope confirmation. Tuesday–Wednesday, set up the five capstone tools plus "sources.json"; Wednesday is also the Midterm Design Review, where I present and defend this architecture, so the tools should be at least partially working by then. Thursday–Friday, test against the 12 evaluation cases.

I ask questions when the tool takes a long time to complete its task (latency issue) or when the Evaluator-optimizer stage is not working properly, which can include accepting incorrect answers or rejecting correct answers. Also when the agent seems to be consuming a lot of tokens.


