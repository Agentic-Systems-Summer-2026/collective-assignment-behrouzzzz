#!/usr/bin/env python3
"""Build Challenge 2 fix — keyword-based relevance filter beats context overload.

Run from the repo root:  python3 bc2-context/fixed_task.py

Instead of stuffing all 30 documents into a single context (overload_task.py),
this script scores each document by simple keyword overlap with the question,
selects the TOP 5, and sends only those to the model.  Fewer tokens → less
drift, lower cost, and the correct three policies reliably make the cut.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, load_prompt, STATS

# Import the canonical document factory and question — no duplication.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from overload_task import make_docs, QUESTION

TOP_K = 5


def _keywords(text: str) -> set[str]:
    """Return lowercase alphabetic words of length >= 4 (skip stop-word noise)."""
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())}


def score_docs(docs: list[str], question: str) -> list[tuple[int, int, str]]:
    """Return list of (doc_number, score, text) sorted by score descending."""
    q_words = _keywords(question)
    scored = []
    for doc in docs:
        # Extract 1-based document number from the header line.
        m = re.match(r"=== DOCUMENT (\d+) ===", doc)
        doc_num = int(m.group(1)) if m else 0
        score = len(_keywords(doc) & q_words)
        scored.append((doc_num, score, doc))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def main():
    docs = make_docs()
    scored = score_docs(docs, QUESTION)
    top = scored[:TOP_K]

    print(f"Total documents: {len(docs)}")
    print(f"Selected top {TOP_K} by keyword relevance:")
    for doc_num, score, _ in top:
        print(f"  Document {doc_num:2d}  score={score}")

    selected_blob = "\n\n".join(text for _, _, text in top)
    print(f"\nSending ~{len(selected_blob):,} chars (vs full corpus) to model…")

    answer = chat(
        [{"role": "system", "content": load_prompt("bc2-analyst-fixed.txt")},
         {"role": "user",  "content": selected_blob + "\n\nQUESTION: " + QUESTION}],
        max_tokens=500,
    )

    print("\n--- ANSWER ---")
    print(answer)

    print("\n--- SELECTED DOCUMENTS (doc number : relevance score) ---")
    for doc_num, score, _ in top:
        print(f"  Doc {doc_num:2d} : {score}")

    print(f"\nSTATS: {STATS}")

    print("\nGround truth: AS-7 (written approval + on-call contact, 72h max), "
          "AS-18 (append-only logs, 90-day retention), AS-24 (read-only creds / "
          "data-owner sign-off). Expired AS-12 (12h) and rescinded AS-27 (24h, "
          "verbal approval) must NOT be cited.")


if __name__ == "__main__":
    main()
