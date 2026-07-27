#!/usr/bin/env python3
"""Build Challenge 1 starter — a tool-calling agent you will extend.

Run:  cd bc1-tools && python3 agent.py "what's in my notes about the demo?"

What works now: a loop where the model chooses tools as JSON actions, with a
full end-to-end trace printed for every step (request size → chosen tool →
result size → next step).

YOUR JOB (see README.md):
  1. Add 2–3 custom tools of your own design (marked TODO below).
  2. Redesign one tool interface to be token-efficient, and show the
     before/after in your write-up. `search_notes_verbose` is deliberately
     wasteful — it returns whole documents when a snippet would do.
"""
import json
import pathlib
import re
import sys

from common.llm import chat, load_prompt, STATS

DATA = pathlib.Path(__file__).resolve().parent / "data"
MAX_STEPS = 12

TOOLS_SPEC = """Available tools (reply with ONE JSON object per turn):
{"tool": "list_notes"}                          -> filenames in the notes folder
{"tool": "search_notes_verbose", "query": "x"}  -> FULL TEXT of every note containing x (wasteful — improve me!)
{"tool": "search_notes_snippet", "query": "x"}  -> list of {"file": "<name>", "line": "<matching line>"} objects (token-efficient)
{"tool": "word_count", "name": "<file>"}        -> number of words in the named note
{"tool": "note_writer", "name": "<file>", "text": "<content>"}  -> write text to a new note in the data folder, returns confirmation
{"tool": "read_note", "name": "<file>"}         -> full text of one note
{"tool": "finish", "answer": "<final answer>"}  -> end the task
"""
# TODO(you): add 2-3 custom tools. Ideas: word_count, a calculator,
# a token-efficient search that returns (filename, matching line) pairs,
# a note-writer. Update TOOLS_SPEC *and* run_tool together — the spec is
# the model's only knowledge of your interface.

# My selected custom tools:
# 1.search_notes_snippet(query) -> returns (filename, matching_line) pairs instead of full documents;
#     the agent needs this to find relevant info without paying the token cost of whole notes.
# 2.word_count(name) -> returns the number of words in the given note file;
#     the agent needs this to answer length-comparison questions without reading full text into context.
# note_writer(name, text) -> writes text to a new note file and returns confirmation;
#     the agent needs this to persist findings or create summary notes as part of a multi-step task.


def run_tool(act: dict) -> str:
    t = act.get("tool")
    if t == "list_notes":
        return json.dumps(sorted(p.name for p in DATA.glob("*.txt")))
    if t == "search_notes_verbose":
        q = act.get("query", "").lower()
        out = {p.name: p.read_text() for p in DATA.glob("*.txt")
               if q in p.read_text().lower()}
        return json.dumps(out) if out else "no matches"
    if t == "search_notes_snippet":
        q = act.get("query", "").lower()
        hits = []
        for p in sorted(DATA.glob("*.txt")):
            for line in p.read_text().splitlines():
                if q in line.lower():
                    hits.append({"file": p.name, "line": line})
        return json.dumps(hits) if hits else "no matches"
    if t == "word_count":
        p = DATA / pathlib.Path(act.get("name", "")).name
        if not p.exists():
            return "ERROR: no such note"
        count = len(p.read_text().split())
        return json.dumps({"file": p.name, "word_count": count})
    if t == "note_writer":
        name = pathlib.Path(act.get("name", "")).name
        if not name:
            return "ERROR: no filename provided"
        p = DATA / name
        if p.exists():
            return f"ERROR: note '{name}' already exists"
        p.write_text(act.get("text", ""))
        return json.dumps({"status": "ok", "file": name, "message": f"Note '{name}' written successfully"})
    if t == "read_note":
        p = DATA / pathlib.Path(act.get("name", "")).name
        return p.read_text() if p.exists() else "ERROR: no such note"
    return "ERROR: unknown tool " + repr(t)


def _first_json_object(text: str) -> dict:
    """First complete JSON object in the model's reply, ignoring anything after.

    Replaces `re.search(r"\\{.*\\}", ...)`, which was greedy: when the model
    emitted two objects in one turn it captured from the first `{` to the last
    `}` and json.loads raised "Extra data". A BC4 eval sweep hit this on 9 of
    28 cases — it needs the model to emit two objects, which is occasional
    rather than systematic, so hand-testing never provoked it.

    The obvious fix, making the pattern non-greedy with `.*?`, trades one bug
    for another: it stops at the first `}`, so `{"tool": "finish", "answer":
    {"a": 1}}` gets truncated to invalid JSON. raw_decode instead parses
    forward from the first `{` and stops at the end of one complete object,
    which handles nesting, trailing objects, leading prose and code fences
    alike.
    """
    i = text.find("{")
    if i == -1:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[i:])
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}


def run_task(task: str, verbose: bool = True) -> str:
    """Run one task to completion and RETURN the final answer.

    Extracted from main() so the agent can be called from other code — the
    BC4 eval harness needs a function it can call with a prompt and get a
    string back, which a print-and-exit main() cannot provide.

    main() now calls this, so running `python3 agent.py "..."` behaves exactly
    as before: same trace, same ANSWER line, same STATS.

    Returns the finish answer, or a marker if the loop hit MAX_STEPS. The
    marker is deliberately a distinctive string rather than "" so that an
    eval case failing this way is visibly different from one that merely
    returned something wrong.
    """
    msgs = [{"role": "system", "content": load_prompt("bc1-agent-system.txt")},
            {"role": "user", "content": TOOLS_SPEC + "\nTASK: " + task}]
    for step in range(1, MAX_STEPS + 1):
        out = chat(msgs)
        act = _first_json_object(out)
        if verbose:
            print(f"\u2500\u2500 step {step}: request\u2248{sum(len(x['content']) for x in msgs)} chars"
                  f" \u2192 chose {act.get('tool')} {({k: v for k, v in act.items() if k not in ('tool', 'answer')})}")
        if act.get("tool") == "finish":
            answer = act.get("answer", "")
            if verbose:
                print("\nANSWER:", answer)
            return answer
        obs = run_tool(act)
        if verbose:
            print(f"          tool returned {len(obs)} chars")
        msgs += [{"role": "assistant", "content": out},
                 {"role": "user", "content": "OBSERVATION:\n" + obs}]
    if verbose:
        print("hit step limit without finishing")
    return "STEP_LIMIT_REACHED"


def main():
    task = " ".join(sys.argv[1:]) or "Summarize what my notes say about the capstone demo."
    run_task(task, verbose=True)
    print(f"\nSTATS: {STATS}")


if __name__ == "__main__":
    main()