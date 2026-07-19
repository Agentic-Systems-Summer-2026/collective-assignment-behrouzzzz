# Build Journal

One short entry per build — all five Build Challenges plus the smaller daily
builds. Four to eight sentences each: this is a lab notebook, not an essay.
It is also your AI-use disclosure record for the course. Graded on
completeness and honesty about failures, not polish. (50 pts, due Aug 6.)

Template per entry:

## Day N — <build name>
- **What I built:**
- **What failed:**
- **What I changed:**
- **Where AI helped, and how I verified its output:**

---

## Day 1 — Lab 0 (example format; replace with your own)
- **What I built:** connected my Codespace to OpenRouter and ran the end-to-end demo.
- **What failed:** first run rejected my key — I had pasted it with a trailing space.
- **What I changed:** re-ran `bash scripts/set-key.sh` and re-ran the gateway task.
- **Where AI helped, and how I verified its output:** asked the TUI to explain the agent loop; cross-checked its claims against the gateway log lines.



## Day 2 - Mini-Build: Workflow vs. Agent

| Run | Version  | Calls | Tokens | Turns | Score /7 | Notes |
|-----|----------|-------|--------|-------|----------|-------|
| 1   | workflow | 3     | 737    | n/a   | 7        | Clean run, no issues |
| 2   | workflow | 3     | 803    | n/a   | 7        | Slightly more tokens, same correctness |
| 3   | workflow | 3     | 737    | n/a   | 7        | Identical to Run 1 |
| 4   | agent    | 4     | 2608   | 4     | 4        | Dropped the health inspection item entirely; espresso deadline field got overwritten with a duplicate "Owner:" label instead of the deadline |
| 5   | agent    | 8     | 6213   | 8     | 0        | Never said DONE, hit the 8-turn cap; last reply was just "TOOL RESULT: 1" — got stuck in a loop |
| 6   | agent    | 8     | 6213   | 8     | 0        | Identical failure to Run 5 (same stats) — stuck again, no final answer produced |

Verdict - for THIS task I would ship the (workflow) because: the workflow scored a perfect 7/7 on all three runs with far fewer tokens, while the agent only succeeded once (4/7, not even a perfect score) and completely failed twice (0/7), getting stuck without ever producing a final answer.
Cost: the agent used far more tokens — roughly 2,600 to 6,200 tokens per run, compared to about 750-800 for the workflow (3-8x more expensive).
Reliability: the workflow was perfectly consistent (7/7 all three times). The agent was unreliable — one partial success and two total failures where it never completed the task within the turn limit.
One thing that surprised me: how badly the agent could get stuck — two out of three runs ended with it repeatedly calling a tool (count_items, returning "1") without ever producing a DONE response, even though the protocol was clearly spelled out in the system prompt.