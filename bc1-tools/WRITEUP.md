# 1.Tool Designs

## search_notes_snippet(query)
Returns matching lines paired with their filename, instead of full documents.
I built this to fix the waste in "search_notes_verbose".

## word_count(name)
Returns the word count for a single note file.
The agent needs this for any question about note length, without pulling the full text into context just to count words.

## note_writer(name, text)
Writes text to a new note file and returns a confirmation.
The agent needs this to save output, like a reminder or a summary, as part of a task.



# 2.Trace — Full End-to-End Run

repo/bc1-tools $ python3 agent.py "what do my notes say about the demo?"
── step 1: request≈724 chars → chose list_notes {}
          tool returned 71 chars
── step 2: request≈831 chars → chose search_notes_verbose {'query': 'demo'}
          tool returned 668 chars
── step 3: request≈1562 chars → chose None {}
          tool returned 24 chars
── step 4: request≈1988 chars → chose finish {}

ANSWER: Your notes indicate you're planning a capstone demo featuring a helpdesk ticket triage agent. The demo should include a live run, visible trace, and rollback story, fitting within eight minutes. A current blocker is the lack of an embedding endpoint on OpenRouter, limiting retrieval work to keyword-only searches.

STATS: {'calls': 4, 'tokens': 1534, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "search my notes for anything about the demo, but be efficient about it"
── step 1: request≈889 chars → chose search_notes_snippet {'query': 'demo'}
          tool returned 361 chars
── step 2: request≈1312 chars → chose read_note {'name': 'capstone-brainstorm.txt'}
          tool returned 296 chars
── step 3: request≈1677 chars → chose read_note {'name': 'standup-notes.txt'}
          tool returned 308 chars
── step 4: request≈2048 chars → chose None {}
          tool returned 24 chars
── step 5: request≈2780 chars → chose finish {}

ANSWER: Found notes about your demo: a helpdesk triage agent with live run, visible trace, and rollback story, fitting in 8 minutes. Main technical constraint is keyword-only retrieval due to missing OpenRouter embedding endpoint.

STATS: {'calls': 5, 'tokens': 2607, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "how many words are in my capstone-brainstorm notes?"
── step 1: request≈955 chars → chose list_notes {}
          tool returned 71 chars
── step 2: request≈1062 chars → chose word_count {'name': 'capstone-brainstorm.txt'}
          tool returned 53 chars
── step 3: request≈1186 chars → chose finish {}

ANSWER: There are 47 words in your capstone-brainstorm notes.

STATS: {'calls': 3, 'tokens': 947, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "write a short note called demo-reminder.txt that says: don't forget to test the rollback flow before the demo"
── step 1: request≈1146 chars → chose note_writer {'name': 'demo-reminder.txt', 'text': "don't forget to test the rollback flow before the demo"}
          tool returned 105 chars
── step 2: request≈1382 chars → chose finish {}

ANSWER: Successfully created demo-reminder.txt with the message 'don't forget to test the rollback flow before the demo'.

STATS: {'calls': 2, 'tokens': 742, 'cache_hits': 0}


repo/bc1-tools $ python3 agent.py "what do my notes say about the demo?"
── step 1: request≈1073 chars → chose search_notes_snippet {'query': 'demo'}
          tool returned 458 chars
── step 2: request≈1593 chars → chose read_note {'name': 'capstone-brainstorm.txt'}
          tool returned 296 chars
── step 3: request≈2081 chars → chose read_note {'name': 'demo-reminder.txt'}
          tool returned 54 chars
── step 4: request≈2198 chars → chose read_note {'name': 'standup-notes.txt'}
          tool returned 308 chars
── step 5: request≈2569 chars → chose None {}
          tool returned 24 chars
── step 6: request≈3080 chars → chose finish {}

ANSWER: Your notes mention a capstone demo that should include a live run, visible trace, and rollback story, fitting in eight minutes. The demo idea involves a helpdesk triage agent, but there's a current blocker with OpenRouter's lack of an embedding endpoint, making retrieval work keyword-only for now. You also have a reminder to test the rollback flow before the demo.

STATS: {'calls': 6, 'tokens': 3716, 'cache_hits': 0}

The model picked "note_writer" on its own and on the first step. There was not hard coding on my end. The task was done in two steps.

# 3.Token-Efficiency Redesign (Before/After)

I ran the exact same task twice: once before "search_notes_snippet" existed, and once after.

## Before (model used "search_notes_verbose"):
```
python3 agent.py "what do my notes say about the demo?"
STATS: {'calls': 4, 'tokens': 1534, 'cache_hits': 0}
```
## After (model used "search_notes_snippet"):
```
python3 agent.py "what do my notes say about the demo?"
STATS: {'calls': 6, 'tokens': 3716, 'cache_hits': 0}
```

Which surprised me was that used tokens increased to more than double!!!

The model did choose "search_notes_snippet" first, instead of the old verbose tool. But then it called "read_note" on every single file the snippet search had matched. So the snippet call became an extra step because the model followed own its old behavior, instead of replacing it.

## Takeaway
A more efficient tool doesn't automatically make the agent use it efficiently. The tool description in "TOOLS_SPEC" never told the model it could skip reading the full note after getting a snippet. Wording controls behavior is the real lesson here, not just the tool code itself.

# 4.Delegation Log

## AI used
OpenClaw, running Claude Sonnet 4.6 (Qwen3 Coder 30B as fallback).

## Key prompts
1. "Add a new tool called search_notes_snippet to agent.py. It should take a query string, search all notes, and instead of returning full documents, return just the matching lines paired with their filename. something like a list of (filename, line) pairs. Add it to both TOOLS_SPEC and run_tool so the model can see and use it."
2. "Add a new tool called word_count to agent.py. It should take a note filename, count the words in that note, and return the count. Add it to both TOOLS_SPEC and run_tool."
3. "Add a new tool called note_writer to agent.py. It should take a filename and text content, write that text to a new note file in the data folder, and return a confirmation message. Add it to both TOOLS_SPEC and run_tool."

## One thing the AI got wrong
- Earlier in this project (Mini-Build 0), OpenClaw told me it had created a file, but the file didn't actually exist in my repo — it had built it in its own separate workspace folder instead. I caught it by running "find" from a regular terminal to locate the real file, then moved it into the right place myself.
- Today, the AI's working directory was not "bc1-tools" since when i ran the first promp i faced error below:
```
No agent.py exists yet — and day2-minibuild is an empty dir. I'll create a             
well-structured agent.py from scratch that includes search_notes_snippet alongside     
enough scaffolding for it to make sense. 
```

## How I caught it
- I checked the file system in the left sidebar and also ran the ls command in the terminal to locate and review the file.
- I asked the AI "what is your current directory?"
```
 /home/node/.openclaw/workspace
 ```
Then I asked it to change its working directory: "change your current directory to /home/node/.openclaw/workspace/bc1-tools"