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