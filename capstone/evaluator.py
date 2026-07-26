"""Evaluator-optimizer check for the Literature Review Assistant capstone."""

import os
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, DEFAULT_MODEL as GENERATOR_MODEL, PROVIDER

os.environ.setdefault("EVALUATOR_MODEL", "Gemma4-31B")

MAX_TECHNICAL_RETRIES = 1


def _evaluator_model() -> str:
    model = os.environ.get("EVALUATOR_MODEL", "").strip()
    if not model:
        raise RuntimeError(
            f"EVALUATOR_MODEL is not set. Generator ({PROVIDER}) is currently using "
            f"{GENERATOR_MODEL!r}. Set EVALUATOR_MODEL to a different model."
        )
    if model.lower() == GENERATOR_MODEL.strip().lower():
        raise RuntimeError(
            f"EVALUATOR_MODEL ({model!r}) matches the generator's model "
            f"({GENERATOR_MODEL!r}). Pick a different model."
        )
    return model


def evaluate(question: str, quote: str, source_id: str, original_question: str | None = None) -> dict:
    """
    question: the specific, narrow claim being checked (a single claim's own
        "statement" in the claim-level design -- kept as the primary "question"
        param name for backward compatibility with any single-question caller).
    original_question: the user's actual original question, if this claim is
        one of possibly several claims assembled to answer it. When given, the
        evaluator checks TWO things instead of one: that the quote grounds the
        claim, AND that the claim is actually responsive to what was asked --
        not just a real, verbatim, on-topic-sounding fact about something else
        entirely (e.g. token counts when the question asked about dollar cost).
        Without this, a claim can be perfectly grounded and still misanswer
        the question, and nothing catches it.
    """
    if original_question:
        prompt = (
            "You are a strict fact-checking judge for a literature-review assistant.\n"
            f"Original user question: {original_question}\n"
            f"Proposed claim (one piece of a possibly multi-part answer): {question}\n"
            f'Supporting quote (from source "{source_id}"): "{quote}"\n\n'
            "Check BOTH of the following:\n"
            "1. Does the quote genuinely and directly support the claim (not a paraphrase or "
            "loose association)?\n"
            "2. Is the claim actually responsive to the ORIGINAL question -- the same topic, "
            "the same metric, the same thing being asked about? A claim about a different "
            "metric or a different aspect (e.g. token usage when dollar cost was asked, or "
            "author details when accuracy was asked) is NOT responsive, even if it is a real, "
            "verbatim, well-supported fact from the source.\n"
            "Reply ACCEPT only if BOTH checks pass. Reply with exactly one line:\n"
            "ACCEPT\n"
            "or\n"
            "REJECT: <short reason, and say which of the two checks failed>"
        )
    else:
        prompt = (
            "You are a strict fact-checking judge for a literature-review assistant.\n"
            f"Question: {question}\n"
            f'Proposed quote (from source "{source_id}"): "{quote}"\n\n'
            "Does this quote genuinely and directly answer the question? "
            "Reply with exactly one line:\n"
            "ACCEPT\n"
            "or\n"
            "REJECT: <short reason>"
        )

    model = _evaluator_model()
    attempts = 0
    last_error = None
    response = None
    while attempts <= MAX_TECHNICAL_RETRIES:
        try:
            response = chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                timeout=120,
                temperature=0,
                retries=0,
            )

            if not isinstance(response, str) or not response.strip():
                raise RuntimeError(f"Evaluator returned an empty response: {response!r}")
            break

            break
        except Exception as e:
            last_error = e
            attempts += 1
            if attempts <= MAX_TECHNICAL_RETRIES:
                time.sleep(5)
    else:
        return {
            "ok": False,
            "technical_error": True,
            "reason": f"Evaluator technical failure after {MAX_TECHNICAL_RETRIES} retry: {last_error}",
        }


    text = response.strip()
    if text.upper().startswith("ACCEPT"):
        return {"ok": True}
    if text.upper().startswith("REJECT"):
        reason = text.split(":", 1)[1].strip() if ":" in text else ""
        # A reply cut off mid-sentence still starts with REJECT, so it would
        # otherwise be recorded as a real verdict: it spends the rejection
        # budget and trips the "already rejected for a content reason" guard,
        # poisoning the rest of the run. A real run was ended by the reason
        # "The claim specifies the" -- 23 characters, ending on a determiner.
        # Genuine rejections from this model run ~160 chars and close with
        # sentence punctuation, so an unpunctuated stub is a dropped
        # connection, not a judgement. Reporting it as technical keeps the
        # claim unaccepted either way, but stops an outage from masquerading
        # as a finding.
        if len(reason) < 30 or not reason.endswith((".", "!", ")")):
            return {"ok": False, "technical_error": True,
                    "reason": f"Evaluator reply looks truncated: {text[:80]!r}"}
        return {"ok": False, "reason": reason}
    # Neither verdict word: the evaluator did not answer the question it was
    # asked, which is a malfunction rather than a ruling on the claim. Still
    # fail-safe (nothing is accepted), but recorded honestly.
    return {"ok": False, "technical_error": True,
            "reason": f"Evaluator gave an unparseable response: {text[:80]!r}"}
