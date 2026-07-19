from pathlib import Path
from common.llm import chat, STATS

# Read notes.txt from the same folder as this script
notes_path = Path(__file__).parent / "notes.txt"
notes = notes_path.read_text(encoding="utf-8")

# Step 1: Extract every action item as task / owner / deadline
action_items = chat([
    {"role": "user", "content": (
        "Extract every action item from the notes below as a list of task / owner / deadline. "
        "Use MISSING when an owner or deadline is absent. "
        "Ignore ideas that were explicitly parked.\n\n"
        f"NOTES:\n{notes}"
    )}
])

# Step 2: Flag items that have a MISSING owner or deadline
flags = chat([
    {"role": "user", "content": (
        "Given the action-item list below, output ONLY the items that have a MISSING owner or deadline.\n\n"
        f"ACTION ITEMS:\n{action_items}"
    )}
])

# Step 3: Write a 3-sentence status summary
summary = chat([
    {"role": "user", "content": (
        "Given the action-item list and the flagged items below, write a 3-sentence status summary.\n\n"
        f"ACTION ITEMS:\n{action_items}\n\n"
        f"FLAGGED (missing owner or deadline):\n{flags}"
    )}
])

# Print all results
print("=== ACTION ITEMS ===")
print(action_items)
print("\n=== FLAGS (missing owner / deadline) ===")
print(flags)
print("\n=== SUMMARY ===")
print(summary)
print("\n=== STATS ===")
print(STATS)
