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