
import os
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, DEFAULT_MODEL as GENERATOR_MODEL, PROVIDER 

os.environ.setdefault("EVALUATOR_MODEL", "Gemma4-31B")

MAX_TECHNICAL_RETRIES = 1


def _evaluator_model() -> str:
    """
    """
    model = os.environ.get("EVALUATOR_MODEL", "").strip()
    if not model:
        raise RuntimeError(
            f"EVALUATOR_MODEL is not set. Your generator ({PROVIDER}) is currently using "
            f"{GENERATOR_MODEL!r} (common.llm.DEFAULT_MODEL, i.e. your COURSE_MODEL). Set "
            "EVALUATOR_MODEL to a DIFFERENT model from the same catalog, e.g.:\n"
            '  export EVALUATOR_MODEL="Claude Haiku 3"\n'
            "(or add it as a Codespaces secret alongside LITELLM_API_KEY)."
        )
    if model.lower() == GENERATOR_MODEL.strip().lower():
        raise RuntimeError(
            f"EVALUATOR_MODEL ({model!r}) is the same as the generator's model "
            f"({GENERATOR_MODEL!r}). Pick a different model — using the same one here "
            "defeats the cross-model check the proposal describes."
        )
    return model


def evaluate(question: str, quote: str, source_id: str) -> dict:
    """
    """
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
                retries=0,  # chat() has its own internal retry/backoff (default 2) — disabled
                            # here so this function's own retry loop is the ONLY retry that
                            # happens, matching PROPOSAL.md's "one technical retry" exactly.
            )
            break
        except Exception as e:
            last_error = e
            attempts += 1
            time.sleep(5)
    else:
        return {
            "ok": False,
            "reason": f"Evaluator technical failure after {MAX_TECHNICAL_RETRIES} retry: {last_error}",
        }

    text = response.strip()
    if text.upper().startswith("ACCEPT"):
        return {"ok": True}
    if text.upper().startswith("REJECT"):
        reason = text.split(":", 1)[1].strip() if ":" in text else "No reason given."
        return {"ok": False, "reason": reason}
    return {"ok": False, "reason": f"Evaluator gave an unparseable response, treated as reject: {text!r}"}


if __name__ == "__main__":
    # Manual tests: Case 1 (real, on-topic quote -> should ACCEPT) and
    # Case 5 (real quote, but off-topic -> should REJECT).
    print("Case 1 (should ACCEPT):")
    print(evaluate(
        question="According to Liu et al. (2026), overall, how much more token usage and "
                  "response time did the agent systems require compared to baseline LLMs?",
        quote="consistently requiring more than tenfold the token usage and at least twice "
              "the response time compared to baseline LLMs",
        source_id="Liu2026",
    ))

    print("\nCase 5 (should REJECT — real quote, but off-topic):")
    print(evaluate(
        question="What accuracy did the agent systems achieve on medical benchmarks?",
        quote="Extended author information available on the last page of the article",
        source_id="AbouAli2025",
    ))
