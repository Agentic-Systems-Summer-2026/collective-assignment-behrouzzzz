import re
from pathlib import Path
from common.llm import chat, STATS

# ── Tool definitions ──────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent

def read_notes() -> str:
    """Return the text of notes.txt located next to this script."""
    return (SCRIPT_DIR / "notes.txt").read_text(encoding="utf-8")

def count_items(text: str) -> str:
    """Count action items in text by counting non-empty lines that start with
    a bullet (-, *, •) or a digit, or any non-empty line if none match."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    bullets = [l for l in lines if re.match(r'^[-*•\d]', l)]
    count = len(bullets) if bullets else len(lines)
    return str(count)

def save_output(text: str) -> str:
    """Write text to agent_output.txt next to this script. Returns 'saved'."""
    (SCRIPT_DIR / "agent_output.txt").write_text(text, encoding="utf-8")
    return "saved"

TOOLS = {
    "read_notes": read_notes,
    "count_items": count_items,
    "save_output": save_output,
}

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM = """You are a task-management assistant. Your GOAL is to:
1. Read the project notes using the read_notes tool.
2. Extract every action item as a list of task / owner / deadline.
   Use MISSING for any absent owner or deadline.
   Ignore ideas that were explicitly parked.
3. Identify items that have a MISSING owner or deadline (the "gaps").
4. Write a 3-sentence status summary covering the action items and gaps.
5. Save the final answer (action-item list + gaps + summary) with save_output.

You have exactly three tools:

  read_notes()
    – Returns the full text of the project notes. No arguments.

  count_items(text)
    – Counts how many action items appear in the given text.
      Pass the action-item list as the argument.

  save_output(text)
    – Writes text to agent_output.txt and returns "saved".
      Call this once with your complete final answer.

Protocol — every reply must contain EXACTLY ONE of:

  ACTION: tool_name(arguments)
      Call a tool. For no-argument tools write: ACTION: read_notes()
      For text arguments write the text directly: ACTION: save_output(your text here)

  DONE: <your final answer>
      Emit this only after you have saved the output with save_output.

Rules:
- One ACTION or DONE per reply, nothing else after the keyword line.
- Do not invent tools or skip steps.
- Do not output DONE before calling save_output.
"""

# ── Agent loop ────────────────────────────────────────────────────────────────

MAX_TURNS = 8

conversation = [{"role": "system", "content": SYSTEM}]
conversation.append({"role": "user", "content": "Please begin."})

final_answer = None
turns = 0

for turn in range(MAX_TURNS):
    turns += 1
    reply = chat(conversation)
    conversation.append({"role": "assistant", "content": reply})

    # ── Forgiving parser ──────────────────────────────────────────────────────
    # Strip markdown code fences if present
    cleaned = re.sub(r'```[^\n]*\n?(.*?)```', r'\1', reply, flags=re.DOTALL)

    # Search for ACTION: or DONE: anywhere in the reply (case-insensitive)
    action_match = re.search(
        r'(?i)\bACTION\s*:\s*(\w+)\s*\(([^)]*)\)',
        cleaned
    )
    done_match = re.search(
        r'(?i)\bDONE\s*:\s*(.*)',
        cleaned,
        re.DOTALL
    )

    if action_match:
        tool_name = action_match.group(1).strip()
        raw_arg   = action_match.group(2).strip()

        if tool_name not in TOOLS:
            result = f"ERROR: unknown tool '{tool_name}'"
        else:
            fn = TOOLS[tool_name]
            try:
                result = fn(raw_arg) if raw_arg else fn()
            except TypeError:
                # tool takes no arguments — call without
                try:
                    result = fn()
                except Exception as e:
                    result = f"ERROR: {e}"
            except Exception as e:
                result = f"ERROR: {e}"

        conversation.append({
            "role": "user",
            "content": f"TOOL RESULT: {result}"
        })

    elif done_match:
        final_answer = done_match.group(1).strip()
        break

    else:
        # Neither keyword found — remind the model of the protocol
        conversation.append({
            "role": "user",
            "content": (
                "Your reply did not contain ACTION: or DONE:. "
                "Please follow the protocol: reply with either "
                "ACTION: tool_name(arguments) or DONE: <final answer>."
            )
        })

# ── Output ────────────────────────────────────────────────────────────────────

print("=== FINAL ANSWER ===")
print(final_answer if final_answer else "(no DONE received — last reply below)")
if not final_answer:
    print(conversation[-1]["content"])

print(f"\n=== TURNS USED: {turns} / {MAX_TURNS} ===")
print("\n=== STATS ===")
print(STATS)
