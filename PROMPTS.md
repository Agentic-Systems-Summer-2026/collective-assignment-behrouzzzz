# Prompt Changelog

Prompts are software artifacts. Every prompt lives as a file in `prompts/` —
never inline-only — and **every change gets a line here**: what changed, why,
and the observed effect. BC2's write-up must cite at least two entries.

Format: `YYYY-MM-DD · file · what changed · why · observed effect`

| Date | Prompt file | What changed | Why | Observed effect |
|---|---|---|---|---|
| 2026-07-13 | bc1-agent-system.txt | (seed) initial system prompt from template | starting point | agent answers but tool JSON occasionally wrapped in prose |

## Day 2 — Mini-Build 0
- prompts/day2-workflow.md: "Agent send the chat() function a plain string while it expects a list of message dicts; fixed (workflow.py)"
- prompts/day2-agent.md: "prompt to build the tool-using agent loop (agent.py)"

## Task 7 — Build Challenge 2: Context & Prompt Design
Model = Claude Sonnet 4.6

Create `bc2-context/fixed_task.py`, a fixed version of `overload_task.py` that solves the same context-overload problem at much lower token cost.

- create NEW system prompt file `prompts/bc2-analyst-fixed.txt`; do NOT edit the original `prompts/bc2-analyst.txt`. The starter must stay untouched. The new prompt must explicitly instruct the model to cite only the policies given below, using their exact numbers and details. If a policy is expired or rescinded, ignore it and prefer whichever policy supersedes it, and never invent a provision that isn't in the given text.
- Import make_docs() and QUESTION from bc2-context/overload_task.py so both scripts run over the identical 30 documents.
  Do NOT hardcode or duplicate the documents.
- Import chat, load_prompt, STATS from common.llm the same way `overload_task.py` does, with the same sys.path insert pattern.
- Build a simple keyword-based relevance filter:
  Extract words from QUESTION, score each document by how many of those words appear in its text, and select the TOP 5 highest scoring documents only, not all 30.
- Send only those 5 documents to chat(), using a NEW system prompt file `prompts/bc2-analyst-fixed.txt`.
- At the end, print the answer, the list of the 5 selected document numbers with their relevance scores, and STATS.
- Keep max_tokens=500.