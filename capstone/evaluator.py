"""Evaluator-optimizer check for the Literature Review Assistant capstone."""

import os
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, DEFAULT_MODEL as GENERATOR_MODEL, PROVIDER 

os.environ.setdefault("EVALUATOR_MODEL", "GLM 5.2")

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


def evaluate(question: str, quote: str, source_id: str) -> dict:
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
                timeout=10,
                temperature=0,
                retries=0,
            )
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
        reason = text.split(":", 1)[1].strip() if ":" in text else "No reason given."
        return {"ok": False, "reason": reason}
    return {"ok": False, "reason": f"Evaluator gave an unparseable response, treated as reject: {text!r}"}
