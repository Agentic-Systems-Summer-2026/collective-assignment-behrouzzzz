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

Verdict: For this task, I would ship the workflow. It scored a perfect 7/7 in all three runs and used far fewer tokens. The agent succeeded only once (4/7). It completely failed twice (0/7). It never reached a final answer.
Cost: The agent used far more tokens, about 2,600 to 6,200 per run. The workflow used about 750–800 tokens per run.
Reliability: The workflow was perfectly consistent. It scored 7/7 in all three runs. The agent was unreliable. It had one partial success and two total failures. It never completed the task.
One thing that surprised me: The agent performed much worse than I expected. In two out of three runs, it repeatedly called the 'count_items' tool, which kept returning "1". It never produced a 'DONE' response.

## Day 3 - Capstone Proposal
- **What I built:**
    - I write the capstone proposal.
        - The main challenge is how to import "human-in-the-loop" while automating the whole process as a "loop," not turning it into a "workflow," as well as keeping your agent simple, agile, and efficient!

- **Where AI helped, and how I verified its output:**
    - I used AI to review my proposal.
    - AI tends to complicate the architecture, adding new tools, and claim unrealistic risks/mitigation.
    - AI tends to provide complex test case scenarios that are not aligned with educational projects.
    - Honestly, it takes me too much time to convince the AI to follow my way. ;) 

 
