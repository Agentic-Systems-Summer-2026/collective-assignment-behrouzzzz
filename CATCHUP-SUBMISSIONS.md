# Task 1 — environment verified
── step 1: request≈724 chars → chose list_notes {}
          tool returned 71 chars
── step 2: request≈831 chars → chose search_notes_verbose {'query': 'demo'}
          tool returned 668 chars
── step 3: request≈1562 chars → chose None {}
          tool returned 24 chars
── step 4: request≈2032 chars → chose finish {}

ANSWER: Your notes indicate that your capstone demo will be a live run with a visible trace and rollback story, fitting within eight minutes. The demo concept involves a triage agent for helpdesk tickets, but there's currently a blocker with OpenRouter lacking an embedding endpoint, so retrieval is limited to keyword-only for now.

STATS: {'calls': 4, 'tokens': 1560, 'cache_hits': 0}

# Task 2 — orientation reading notes
1. What is the actual difference between a workflow and an agent?
Workflows provide predictability, while agents offer flexibility for open-ended tasks. A workflow follows predefined code paths. The developer decides the sequence of steps and the tools to use in advance. In contrast, an agent allows the LLM to decide which actions and tools to use. It also decides the order of those actions to achieve the goal.

2. When is an agent the wrong choice?
An agent is the wrong choice when a simple solution or a deterministic workflow can reliably solve the problem. For repeatable tasks with predictable steps, workflows are usually the best choice.

3. What is a tool, in the technical sense used here?
Tools help an agent perceive its environment and act on it. A tool is an external capability that lets an LLM interact with its environment. Examples include searching the web, running Python code, querying databases, and calling APIs. Tools allow agents to observe, take action, and modify their environment.

4. What makes an agentic loop terminate safely?
A safe agentic loop should have one or more of the following:
- Clear goal metrics.
- Explicit stopping conditions.
- Limits on time, cost, or iterations.
It should also run in a controlled environment with proper permissions and verification. This prevents the agent from running indefinitely.

5. What is one failure mode you expect to encounter?
To my mind, one likely failure mode is selecting the wrong tool. This can lead to unnecessary iterations or incorrect results.

# Task 3 — Mini-Build 0 submission". Complete

Repo: https://github.com/Agentic-Systems-Summer-2026/collective-assignment-behrouzzzz


| Run | Version  | Calls | Tokens | Turns | Score /7 | Notes |
|-----|----------|-------|--------|-------|----------|-------|
| 1   | workflow | 3     | 737    | n/a   | 7        | Clean run, no issues |
| 2   | workflow | 3     | 803    | n/a   | 7        | Slightly more tokens, same correctness |
| 3   | workflow | 3     | 737    | n/a   | 7        | Identical to Run 1 |
| 4   | agent    | 4     | 2608   | 4     | 4        | Dropped the health inspection item entirely; espresso deadline field got overwritten with a duplicate "Owner:" label instead of the deadline |
| 5   | agent    | 8     | 6213   | 8     | 0        | Never said DONE, hit the 8-turn cap; last reply was just "TOOL RESULT: 1" — got stuck in a loop |
| 6   | agent    | 8     | 6213   | 8     | 0        | Identical failure to Run 5 (same stats) — stuck again, no final answer produced |

Verdict: For this task, I would ship the workflow. It scored a perfect 7/7 in all three runs and used far fewer tokens. The agent succeeded only once (4/7). It completely failed twice (0/7). It never reached a final answer.
Cost: The agent used far more tokens, about 2,600 to 6,200 per run. The workflow used about 750–800 tokens per run.
Reliability: The workflow was perfectly consistent. It scored 7/7 in all three runs. The agent was unreliable. It had one partial success and two total failures. It never completed the task.
One thing that surprised me: The agent performed much worse than I expected. In two out of three runs, it repeatedly called the 'count_items' tool, which kept returning "1". It never produced a 'DONE' response.



# Task 4  Canvas assignment: "Build Challenge 1 — Tool/Function Calling"

Repo: https://github.com/Agentic-Systems-Summer-2026/collective-assignment-behrouzzzz

# 4.1.Tool Designs

## search_notes_snippet(query)
Returns matching lines paired with their filename, instead of full documents.
I built this to fix the waste in "search_notes_verbose".

## word_count(name)
Returns the word count for a single note file.
The agent needs this for any question about note length, without pulling the full text into context just to count words.

## note_writer(name, text)
Writes text to a new note file and returns a confirmation.
The agent needs this to save output, like a reminder or a summary, as part of a task.



# 4.2.Trace — Full End-to-End Run

repo/bc1-tools $ python3 agent.py "what do my notes say about the demo?"
── step 1: request≈724 chars → chose list_notes {}
          tool returned 71 chars
── step 2: request≈831 chars → chose search_notes_verbose {'query': 'demo'}
          tool returned 668 chars
── step 3: request≈1562 chars → chose None {}
          tool returned 24 chars
── step 4: request≈1988 chars → chose finish {}

ANSWER: Your notes indicate you're planning a capstone demo featuring a helpdesk ticket triage agent. The demo should include a live run, visible trace, and rollback story, fitting within eight minutes. A current blocker is the lack of an embedding endpoint on OpenRouter, limiting retrieval work to keyword-only searches.

STATS: {'calls': 4, 'tokens': 1534, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "search my notes for anything about the demo, but be efficient about it"
── step 1: request≈889 chars → chose search_notes_snippet {'query': 'demo'}
          tool returned 361 chars
── step 2: request≈1312 chars → chose read_note {'name': 'capstone-brainstorm.txt'}
          tool returned 296 chars
── step 3: request≈1677 chars → chose read_note {'name': 'standup-notes.txt'}
          tool returned 308 chars
── step 4: request≈2048 chars → chose None {}
          tool returned 24 chars
── step 5: request≈2780 chars → chose finish {}

ANSWER: Found notes about your demo: a helpdesk triage agent with live run, visible trace, and rollback story, fitting in 8 minutes. Main technical constraint is keyword-only retrieval due to missing OpenRouter embedding endpoint.

STATS: {'calls': 5, 'tokens': 2607, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "how many words are in my capstone-brainstorm notes?"
── step 1: request≈955 chars → chose list_notes {}
          tool returned 71 chars
── step 2: request≈1062 chars → chose word_count {'name': 'capstone-brainstorm.txt'}
          tool returned 53 chars
── step 3: request≈1186 chars → chose finish {}

ANSWER: There are 47 words in your capstone-brainstorm notes.

STATS: {'calls': 3, 'tokens': 947, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "write a short note called demo-reminder.txt that says: don't forget to test the rollback flow before the demo"
── step 1: request≈1146 chars → chose note_writer {'name': 'demo-reminder.txt', 'text': "don't forget to test the rollback flow before the demo"}
          tool returned 105 chars
── step 2: request≈1382 chars → chose finish {}

ANSWER: Successfully created demo-reminder.txt with the message 'don't forget to test the rollback flow before the demo'.

STATS: {'calls': 2, 'tokens': 742, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "what do my notes say about the demo?"
── step 1: request≈1073 chars → chose search_notes_snippet {'query': 'demo'}
          tool returned 458 chars
── step 2: request≈1593 chars → chose read_note {'name': 'capstone-brainstorm.txt'}
          tool returned 296 chars
── step 3: request≈2081 chars → chose read_note {'name': 'demo-reminder.txt'}
          tool returned 54 chars
── step 4: request≈2198 chars → chose read_note {'name': 'standup-notes.txt'}
          tool returned 308 chars
── step 5: request≈2569 chars → chose None {}
          tool returned 24 chars
── step 6: request≈3080 chars → chose finish {}

ANSWER: Your notes mention a capstone demo that should include a live run, visible trace, and rollback story, fitting in eight minutes. The demo idea involves a helpdesk triage agent, but there's a current blocker with OpenRouter's lack of an embedding endpoint, making retrieval work keyword-only for now. You also have a reminder to test the rollback flow before the demo.

STATS: {'calls': 6, 'tokens': 3716, 'cache_hits': 0}

The model picked "note_writer" on its own and on the first step. There was not hard coding on my end. The task was done in two steps.

# 4.3.Token-Efficiency Redesign (Before/After)

I ran the exact same task twice: once before "search_notes_snippet" existed, and once after.

## Before (model used "search_notes_verbose"):
```
python3 agent.py "what do my notes say about the demo?"
STATS: {'calls': 4, 'tokens': 1534, 'cache_hits': 0}
```
## After (model used "search_notes_snippet"):
```
python3 agent.py "what do my notes say about the demo?"
STATS: {'calls': 6, 'tokens': 3716, 'cache_hits': 0}
```

Which surprised me was that used tokens increased to more than double!!!

The model did choose "search_notes_snippet" first, instead of the old verbose tool. But then it called "read_note" on every single file the snippet search had matched. So the snippet call became an extra step because the model followed own its old behavior, instead of replacing it.

## Takeaway
A more efficient tool doesn't automatically make the agent use it efficiently. The tool description in "TOOLS_SPEC" never told the model it could skip reading the full note after getting a snippet. Wording controls behavior is the real lesson here, not just the tool code itself.

# 4.4.Delegation Log

## AI used
OpenClaw, running Claude Sonnet 4.6 (Qwen3 Coder 30B as fallback).

## Key prompts
1. "Add a new tool called search_notes_snippet to agent.py. It should take a query string, search all notes, and instead of returning full documents, return just the matching lines paired with their filename. something like a list of (filename, line) pairs. Add it to both TOOLS_SPEC and run_tool so the model can see and use it."
2. "Add a new tool called word_count to agent.py. It should take a note filename, count the words in that note, and return the count. Add it to both TOOLS_SPEC and run_tool."
3. "Add a new tool called note_writer to agent.py. It should take a filename and text content, write that text to a new note file in the data folder, and return a confirmation message. Add it to both TOOLS_SPEC and run_tool."

## One thing the AI got wrong
- Earlier in this project (Mini-Build 0), OpenClaw told me it had created a file, but the file didn't actually exist in my repo — it had built it in its own separate workspace folder instead. I caught it by running "find" from a regular terminal to locate the real file, then moved it into the right place myself.
- Today, the AI's working directory was not "bc1-tools" since when i ran the first promp i faced error below:
```
No agent.py exists yet — and day2-minibuild is an empty dir. I'll create a             
well-structured agent.py from scratch that includes search_notes_snippet alongside     
enough scaffolding for it to make sense. 
```

## How I caught it
- I checked the file system in the left sidebar and also ran the ls command in the terminal to locate and review the file.
- I asked the AI "what is your current directory?"
```
 /home/node/.openclaw/workspace
 ```
Then I asked it to change its working directory: "change your current directory to /home/node/.openclaw/workspace/bc1-tools"


# Task 5  Canvas assignment: "Project Idea Memo"

Repo: https://github.com/Agentic-Systems-Summer-2026/collective-assignment-behrouzzzz

# Project Idea Memo

## 1. The Use Case
I want to build a "literature review assistant". It takes a set of source documents such as papers, articles, and reports. It answers questions about them with citations back to the specific source. Instead of manually reading through a stack of PDFs to write annotations, the system reads them and always tells me which document each claim came from.
This use case directly aligns with the graduate bibliography requirement. Every annotation I write for Task 8 needs to cite its source and explain its relevance to my capstone. This tool automates the first draft of that process, while I still review and finalize each entry myself.

## 2. Why an Agent, Not a Workflow
A fixed workflow makes sense when every step is known in advance and never changes. That's not match this task. Which source is relevant to a given question, and how much of it to quote, are not fixed. It depends on the question and the document. An agent can make it, because it decides its next step based on what it read, not on a predefined workflow which I wrote in advance.
Task 3 showed me this difference directly. My fixed workflow scored 7 out of 7 on all three runs, using around 750 tokens each time. It was reliable because the task itself was fixed, including extract, flag, summarize, always in that order. In contrast, the agent version was less predictable. It succeeded once at 4 out of 7 while failing twice. The agent never produced a final answer. The meeting note task was too structured to need judgment. 
The literature review task requires judgment because it includes deciding which passage answers a question and how to cite it. 
I'm accepting more variability in exchange for a set of tools that can actually handle open ended questions across a set of sources.

## 3. Human-in-the-Loop Plan
The agent never gets the final word. Here's where the human is in the loop:
- Before it runs: human chooses which sources go into the document set. The agent only sees what the human gives it.
- After each annotation: human reviews the citation before adding it to the final paper. If the agent points to the wrong document, or misreads a claim, the human catches it before it will be added into a bibliography.
- Rollback: every draft annotation gets written to a separate file first, never directly into the final bibliography document. Nothing reaches the graded deliverable without being copied over by a human.
This keeps the agent useful for the tedious part (reading and drafting), while humans stay responsible.

# Task 6  Canvas assignment: "Capstone — Proposal"

Repo: https://github.com/Agentic-Systems-Summer-2026/collective-assignment-behrouzzzz

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

# Task 7 — Build Challenge 2: Context & Prompt Design

Repo: https://github.com/Agentic-Systems-Summer-2026/collective-assignment-behrouzzzz

## 1. The Failure — `overload_task.py` (Starter= Before)
The starter feeds all 30 policy documents (~115,802 chars) into a single request. The result of 3 runs of 'overload_task.py` are presented in the table below:

| Run | Model | Tokens | AS-7 | AS-18 | AS-24 | Trap cited? |
|-----|-------|--------|:---:|:---:|:---:|:---:|
| 1 | Claude Sonnet 4.6 | 24,811 | Yes | Yes | Missing | No |
| 2 | gemma4-small-12B | 24,800 | Yes | Yes | Missing | No |
| 3 | gemma4-small-12B | 24,800 | Yes | Yes | Missing | No |

### Failure Reproduced And Explained
Based on the results, the actual failure mode differs. Across all 3 runs and both models, the third relevant document (AS-24, "access to a shared drive") was silently omitted from the answer, even though the question explicitly mentions "access to a shared drive". The model found and correctly quoted the two policies AS-7 and AS-18, emphasizing unattended runtime and logging. AS-24 is a miss because of the context-overload symptom. What is interesting is that it didn't invent anything and didn't cite a wrong policy. Token cost held steady at ~24,800–24,811 per query, which is close to the assignment's ~25k estimate, regardless of which model was used.

## 2. The Fix — `fixed_task.py` ("After")
### Strategy
 I use Just-in-time retrieval plus a tightened system prompt (system-prompt altitude). 
The Just-in-time retrieval helps to find Relevant policies, leading to mitigating overloading the LLM model. The tightened system prompt is applied to clear rules preventing the selection of the wrong policies.
The question's words are scored against every document's text, and only the top 5 highest-scoring documents are sent to the model. The system prompt (`prompts/bc2-analyst-fixed.txt`, new file, starter left untouched) adds explicit rules: cite only what's given, ignore anything marked EXPIRED or RESCINDED and prefer whatever supersedes it, never invent a provision.
The keyword filter reliably selects the same 5 documents every run — AS-7, AS-12, AS-18, AS-24, AS-27. What interested me was that all received a score of 4. It happened because either the traps share vocabulary with the real policies or our score range is tight. To my mind, it also means that retrieval alone does not separate the real policies from the traps. So, that distinction must be made entirely by the system prompt's explicit EXPIRED/RESCINDED rule.

### Run result (After) 
| Run | Model | Tokens | Correct citations | Trap cited? |
|-----|-------|--------|---------------------|:---:|
| 1 | gemma4-small-12B | 631 | AS-7, AS-18, AS-24 (all correct) | No |
| 2 | gemma4-small-12B | 631 | AS-7, AS-18, AS-24 (all correct) | No |
| 3 | Claude Sonnet 4.6 | 631 | AS-7, AS-18, AS-24 (all correct) | No |

The result shows that there is consistency across 3 runs and both models, which proves that the fix does not depend on a stronger model to work.

## 3. Before / After Comparison
| | Before (starter) | After (fixed) |
|---|---|---|
| Avg. tokens/query | ~24,804 | 631 |
| Correct citation set (AS-7/18/24) | 0/3 runs (AS-24 always missing) | 3/3 runs |
| Trap citations (AS-12/27) | 0/3 runs | 0/3 runs |
| Token reduction | — | **~97.5% (≈39× cheaper)** |

## 4. Prompt Changelog
See `PROMPTS.md` for full entries. Cited here as evidence of the fix:

1. `prompts/bc2-analyst.txt` (starter, left unmodified) 
The baseline prompt used by `overload_task.py`. Kept intact per assignment instructions so the before/after comparison stays honest.
2. `prompts/bc2-analyst-fixed.txt` (new file) 
Adds the explicit EXPIRED/RESCINDED exclusion rule, the ban on invented provisions, and the "say so if the documents don't answer part of the question" rule.

## 5. Takeaway
The real failure was a real, relevant document going missing without any error or wrong citation to flag it. It is really worse because a wrong citation is traceable while a silent omission isn't. On the one hand, retrieval (top-5 by keyword score) fixed the volume problem and significantly decreased tokens by ~97.5%. On the other hand, it still handed the model both real and trap documents side by side. This issue is fixed by the prompt's explicit exclusion rule. 
All in all, cheaper and narrower context didn't automatically mean correct; the wording still had to do the job.


