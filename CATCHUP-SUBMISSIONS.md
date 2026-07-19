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
