# Build Challenge 2: Context & Prompt Design

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


