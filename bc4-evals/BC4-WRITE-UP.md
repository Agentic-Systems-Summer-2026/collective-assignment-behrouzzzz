# Build Challenge 4 — Evaluation
- Built the harness for the capstone. The "harness.py" wired to the capstone agent. 
- CI regression gate on GitHub Actions running with the OU LiteLLM Sandbox.


## Test Cases
- 15 cases created to cover all 5 source papers including a refusal case and a formatting one.
- I couldn't use the  part! It seems that  
- I only used "must_not_contain" in one case. It is in the "case 11" where I am sure there is no right answer and I am also able to refer to a specific sign ($).


## Sweep Report
- Starting sweep first run failed in 12 seconds on a missing "pypdf" dependency. The starter workflow's install step didn't cover.
- Difficulty in setting up the evaluator model due to the long latency in receiving the response. So, I tryed different models with limited case number (3) and finally choosing "Qwen3 32B".

### Test Sweep
- 14/15 cases pass (93%, threshold 80%). 
- The one failure is diagnosed ("du_optimization_categories"). The capstone evaluator ran out of its turn budget (8 tries). It seems to be related to phrasing words against a small turn budget.

### Green
- Link: https://github.com/Agentic-Systems-Summer-2026/collective-assignment-behrouzzzz/actions/runs/30308665721

### Broken
- Link: https://github.com/Agentic-Systems-Summer-2026/collective-assignment-behrouzzzz/actions/runs/30309584196
- This run Failed because two of 5 cases had their must_contain values changed ("15.5"→"99.9" & "brain"→"heart"). The agent never finds new values  in answers to confirm them.


## Judge calibration
- 9/9 agreement
- To my mind it happen because the judge criteria and must-contain make it realy easy to diagnose the right answer. Plus, Because the items are not complex and conceptual, and this goes back to our agent, which should return the exact text of the article to the user.
- A second check with 4 deliberately wrong answers was applyed to test the sample correctly rejected with an accurate reason.

| case | your label | judge label | agree? | question |
|---|---|---|---|---|
| liu_tokens_1 | PASS | PASS | yes | According to Liu et al. (2026), overall, how much more token... |
| liu_multimodal_hle | PASS | PASS | yes | According to Liu et al. (2026), what accuracy did the agent ... |
| xi_framework | PASS | PASS | yes | What three-component conceptual framework do Xi et al. propo... |
| qin_modules | PASS | PASS | yes | According to Qin and Jin, what are the key modules that make... |
| liu_tokens_2_rerun | PASS | PASS | yes | According to Liu et al. (2026), overall, how much more token... |
| abouali_paradigm_names | PASS | PASS | yes | What are the two paradigm names Abou Ali et al. use to categ... |
| paradigm_relation | PASS | PASS | yes | How does the symbolic-vs-neural paradigm split (Abou Ali et ... |
| two_way_classification | PASS | PASS | yes | Which two of these surveys propose a two-way classification ... |
| openmanus_accuracy | PASS | PASS | yes | What overall accuracy did OpenManus achieve on MedAgentsBenc... |


## Delegation Log

### which AI
- Claude Sonnet (It took several runs to get to the stable code!)

### My Key Prompts
Your main goal is to help me successfully complete the challenge.

Principles:
- Prioritize satisfying the BC4 requirements over building a complex system.
- Avoid unnecessary redesign, refactoring, frameworks, or dependencies.
- Prefer minimal changes to the existing implementation.

Strategy:
- First understand the requirements and existing implementation.
- Before making major changes, explain the proposed approach and why it is the simplest solution.
- Make only necessary changes.
- Test frequently and fix only issues required.
- Explain important decisions before implementation.
- Ask me when information is needed.
- Do not optimize for complexity.
 

### What It Got Wrong
- First "harness.py" edit broke immediately: removed the `chat` import while rewiring "target()". 
- "NameError": name 'chat' is not defined` on the very first run.
- The workflow install step was missed on the first Starting sweep run: the "pypdf" dependency gap wasn't recognized.

### Verifying The Result
- The answers was checked with the text of the 5 PDFs.