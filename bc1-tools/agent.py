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


def main():
    task = " ".join(sys.argv[1:]) or "Summarize what my notes say about the capstone demo."
    msgs = [{"role": "system", "content": load_prompt("bc1-agent-system.txt")},
            {"role": "user", "content": TOOLS_SPEC + "\nTASK: " + task}]
    for step in range(1, MAX_STEPS + 1):
        out = chat(msgs)
        m = re.search(r"\{.*\}", out, re.S)
        act = json.loads(m.group(0)) if m else {}
        print(f"── step {step}: request≈{sum(len(x['content']) for x in msgs)} chars"
              f" → chose {act.get('tool')} {({k: v for k, v in act.items() if k not in ('tool', 'answer')})}")
        if act.get("tool") == "finish":
            print("\nANSWER:", act.get("answer", ""))
            break
        obs = run_tool(act)
        print(f"          tool returned {len(obs)} chars")
        msgs += [{"role": "assistant", "content": out},
                 {"role": "user", "content": "OBSERVATION:\n" + obs}]
    else:
        print("hit step limit without finishing")
    print(f"\nSTATS: {STATS}")


if __name__ == "__main__":
    main()
