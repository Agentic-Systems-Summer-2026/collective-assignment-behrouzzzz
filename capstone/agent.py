"""Autonomous agent loop for the Literature Review Assistant capstone."""

import json
import time
import hashlib
import uuid
from pathlib import Path

import tools
from evaluator import evaluate
from common.llm import chat, STATS

MAX_TURNS = 8  # base budget, proven sufficient for single-source questions (Case 1: 7/8)
TURNS_PER_EXTRA_SOURCE = 4  # extra allowance once a 2nd, 3rd, ... distinct source is touched
MAX_TURNS_HARD_CAP = 20  # absolute ceiling regardless of source count, so cost can't run away
MAX_EVAL_REJECTIONS = 2
MAX_TECHNICAL_FINISH_RETRIES = 3  # a purely-technical finish failure (e.g. an evaluator network
    # timeout, already excluded from MAX_EVAL_REJECTIONS) also must not silently cost a turn from
    # the exploration budget above -- otherwise a network blip on the LAST available turn kills an
    # otherwise-correct answer for a reason that has nothing to do with the model's own choices.
    # This is a small, separately-capped pool of "free" retries so a couple of blips can't sink a
    # run, but a genuinely, permanently down evaluator still can't loop forever.
READ_SOURCE_CHAR_LIMIT = 4000  # caps token cost; full text stays available via search_sources

LOG_DIR = Path(__file__).parent / "logs"

TOOLS_SPEC = """Available tools — reply with exactly ONE JSON object per turn, nothing else:

{"tool": "list_sources"}
    -> [{"file": "...", "id": "..." or null}, ...] every source and its id

{"tool": "search_sources", "query": "keyword"}
    -> [{"file": "...", "line": "..."}, ...] lines containing that EXACT text, across all sources.
       "query" must be a short, distinctive keyword or phrase (1-4 words) likely
       to appear verbatim on a single line — NOT a full sentence or a
       restatement of the question, since a whole sentence almost never
       matches one extracted PDF line exactly. If a search comes up empty,
       try a shorter or different keyword, or use read_source instead.

{"tool": "read_source", "name": "<file, e.g. Liu2026.pdf>"}
    -> {"ok": true, "text": "..."} or {"ok": false, "error": "..."}. For long
       documents "text" may be truncated (an added "truncated": true field
       tells you so) to control cost — if what you need isn't in the
       returned text, use search_sources with a distinctive keyword instead
       of expecting read_source to hand you the whole document. If what you
       need IS in the returned text, look for your answer and quote directly
       in it — do not go back to search_sources for a sentence you already
       have in front of you.

{"tool": "lookup_citation", "source_id": "<id, e.g. Liu2026>"}
    -> {"ok": true, "in_text": "(Author, Year)", "reference": "..."} or an error

{"tool": "finish", "claims": [{"source_id": "<id>", "quote": "<verbatim quote>", "statement": "<a short, self-contained claim this quote supports>"}]}
    -> Submits one or more independent claims. Each claim is checked on its
       own: first that "quote" appears verbatim in that source, then that it
       genuinely supports "statement". A claim that passes is locked in
       permanently for this run — you never need to resubmit or re-check it
       again, even if you're still working on other claims. A claim that
       fails is reported back with its reason; only THAT claim needs fixing.

       Each "quote" must be ONE short, contiguous span — a single sentence
       or clause, ideally well under 200 characters — copied
       character-for-character from a single "line" in a search_sources
       result or a single span of a read_source result. Do not stitch
       multiple sentences into one quote; if a claim needs more than one
       sentence of support, submit it as two separate claim objects instead.

       "statement" is your own words, standalone and self-contained (it will
       appear on its own, tied only to its own source_id — never assume it
       will be read next to any other claim). Do not write "statement" as
       half of a larger comparison that only makes sense combined with
       another claim; each statement must be true and complete by itself.

       You can call finish more than once. Only include NEW or STILL-FAILING
       claims each time — anything already locked in does not need to be
       resent. If you call finish with no new claims (or an empty list) and
       at least one claim has already been locked in, the run ends
       immediately using whatever has been locked in so far — this is how
       you signal "I'm satisfied with what I have, stop here."

       If NO source supports any claim for this question, call finish with
       "claims" omitted (or empty) and "answer": "INSUFFICIENT CONTEXT"
       instead — do this only if nothing has been locked in yet.

    Example showing the JSON SHAPE ONLY (this source_id and text are made up
    placeholders, not real data — never search for or reuse this exact text):
    {"tool": "finish", "claims": [{"source_id": "ExampleSource2099", "quote": "<a sentence copied exactly, character-for-character, from that source's real text>", "statement": "A short, standalone claim this quote supports."}]}
"""

SYSTEM_PROMPT = (
    "You are a literature-review assistant. Answer questions using ONLY the "
    "provided source documents, which you must find yourself using the "
    "tools below — never invent a quote, citation, or fact, and never "
    "answer from general knowledge. You decide which tools to use, in what "
    "order, and how many steps you need — there is no fixed procedure. "
    "Build your answer as one or more independent claims, each backed by "
    "its own verbatim quote from its own source, verified automatically the "
    "moment you submit it; a claim that fails is rejected and you must "
    "revise or drop just that one, while any claim that already passed "
    "stays locked in no matter what else happens later. As soon as you find "
    "a quote that directly supports a claim, submit it — do not keep "
    "searching for a better phrasing or extra confirmation once you already "
    "have one. Do not give up after only one or two failed searches — if "
    "the question names a specific paper or author (e.g. 'Abou Ali et "
    "al.'), use list_sources to find its source_id and call read_source on "
    "it directly instead of guessing more search phrases; a real search "
    "miss just means try a shorter keyword or read the source directly, not "
    "that the answer isn't there. If, after investigating, no source "
    "supports any claim at all, finish with exactly: INSUFFICIENT CONTEXT. "
    "Reply with exactly one JSON object per turn — no prose outside the "
    "JSON."
)


def _source_key(name_or_id: str) -> str:
    return name_or_id[:-4] if name_or_id.lower().endswith(".pdf") else name_or_id


def _effective_max_turns(sources_touched: set) -> int:
    extra = max(0, len(sources_touched) - 1)
    return min(MAX_TURNS_HARD_CAP, MAX_TURNS + TURNS_PER_EXTRA_SOURCE * extra)


def _extract_json(out: str) -> dict:
    start = out.find("{")
    if start == -1:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(out[start:])
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def run_tool(act: dict) -> str:
    t = act.get("tool")

    if t == "list_sources":
        return json.dumps(tools.list_sources())

    if t == "search_sources":
        return json.dumps(tools.search_sources(act.get("query", "")))

    if t == "read_source":
        result = tools.read_source(act.get("name", ""))
        text = result.get("text")
        if result.get("ok") and isinstance(text, str) and len(text) > READ_SOURCE_CHAR_LIMIT:
            result = dict(result)
            result["full_length_chars"] = len(text)
            result["text"] = text[:READ_SOURCE_CHAR_LIMIT]
            result["truncated"] = True
        return json.dumps(result)

    if t == "lookup_citation":
        return json.dumps(tools.lookup_citation(act.get("source_id", "")))

    return json.dumps({"ok": False, "error": f"unknown tool {t!r}"})


def _check_claims(claims: list, state: dict) -> list:
    """
    Checks each claim independently and returns only the ones still failing.
    Permanently records outcomes in state:
      - a claim that passes (fresh, or already cached from an earlier
        attempt this run) is appended to state["accepted_claims"] and its
        (source_id, quote) key is locked into state["verified_keys"] so it
        is never re-verified again, even if resubmitted alongside a
        still-broken claim in a later attempt.
      - a claim that fails for a genuine (non-technical) reason is appended
        to state["rejected_claims"] (for the final transparency section)
        and its key is locked into state["rejected_keys"], so an unchanged
        resubmission is caught instantly without spending another evaluator
        call or risking another network timeout on a quote already known
        to be bad.
    """
    errors = []
    for c in claims:
        source_id = c.get("source_id", "")
        quote = c.get("quote", "")
        statement = c.get("statement", "")
        key = (source_id, quote)

        if key in state["verified_keys"]:
            continue  # already proven good earlier this run - no re-check needed

        if key in state["rejected_keys"]:
            errors.append({
                "source_id": source_id,
                "quote": quote,
                "reason": ("This exact quote was already rejected earlier in this run for a "
                           "content reason. Resubmitting it unchanged will not work — use a "
                           "different, shorter, single-sentence span instead."),
            })
            continue

        verbatim = tools.verify_quote(source_id, quote)
        if not verbatim.get("ok"):
            errors.append({"source_id": source_id, "quote": quote, "reason": verbatim.get("error")})
            state["rejected_keys"].add(key)
            state["rejected_claims"].append({
                "source_id": source_id, "quote": quote, "statement": statement,
                "reason": verbatim.get("error"),
            })
            continue

        # Each claim's own "statement" stands in for the question here — the
        # evaluator judges this specific, narrower claim, not the original
        # (possibly compound) question as a whole.
        verdict = evaluate(question=statement, quote=quote, source_id=source_id)
        if not verdict.get("ok"):
            technical = verdict.get("technical_error", False)
            errors.append({
                "source_id": source_id,
                "quote": quote,
                "reason": verdict.get("reason"),
                "technical_error": technical,
            })
            if not technical:
                state["rejected_keys"].add(key)
                state["rejected_claims"].append({
                    "source_id": source_id, "quote": quote, "statement": statement,
                    "reason": verdict.get("reason"),
                })
            continue

        state["verified_keys"].add(key)
        state["accepted_claims"].append({"source_id": source_id, "quote": quote, "statement": statement})

    return errors


def _truncate(value, limit: int = 800):
    if isinstance(value, str):
        if len(value) > limit:
            return value[:limit] + f"... [truncated, {len(value)} chars total]"
        return value
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value]
    return value


def _write_log(question: str, trace: list, final_answer: str, eval_rejections: int,
                outcome: str, usage: dict, sources_touched: set, effective_max_turns: int,
                accepted_claims: list, rejected_claims: list, turns_charged: int,
                technical_finish_retries: int) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    q_hash = hashlib.sha1(question.encode("utf-8")).hexdigest()[:10]
    timestamp = time.strftime("%Y%m%dT%H%M%S")
    unique = uuid.uuid4().hex[:6]
    path = LOG_DIR / f"{timestamp}_{q_hash}_{unique}.json"
    record = {
        "question": question,
        "final_answer": final_answer,
        "outcome": outcome,
        "turns_charged": turns_charged,
        "turns_total_including_free_technical_retries": len(trace),
        "technical_finish_retries_used": technical_finish_retries,
        "eval_rejections_used": eval_rejections,
        "base_turns": MAX_TURNS,
        "sources_touched": sorted(sources_touched),
        "effective_max_turns": effective_max_turns,
        "max_eval_rejections": MAX_EVAL_REJECTIONS,
        "max_technical_finish_retries": MAX_TECHNICAL_FINISH_RETRIES,
        "usage": usage,
        "accepted_claims": accepted_claims,
        "rejected_claims": rejected_claims,
        "trace": trace,
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def answer_question(question: str, verbose: bool = False) -> str:
    state = {
        "eval_rejections": 0,
        "verified_keys": set(),
        "rejected_keys": set(),
        "accepted_claims": [],
        "rejected_claims": [],
        "technical_finish_retries": 0,
    }
    trace = []
    sources_touched = set()
    start_stats = dict(STATS)
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TOOLS_SPEC + "\nQUESTION: " + question},
    ]

    def finish_run(answer: str, outcome: str, turns_charged: int) -> str:
        usage = {
            "calls": STATS.get("calls", 0) - start_stats.get("calls", 0),
            "tokens": STATS.get("tokens", 0) - start_stats.get("tokens", 0),
            "cache_hits": STATS.get("cache_hits", 0) - start_stats.get("cache_hits", 0),
        }
        cap = _effective_max_turns(sources_touched)
        path = _write_log(question, trace, answer, state["eval_rejections"], outcome, usage,
                           sources_touched, cap, state["accepted_claims"], state["rejected_claims"],
                           turns_charged, state["technical_finish_retries"])
        if verbose:
            print(f"── log written: {path} (usage: {usage}, sources_touched: {sorted(sources_touched)}, "
                  f"effective_max_turns: {cap}, accepted: {len(state['accepted_claims'])}, "
                  f"rejected: {len(state['rejected_claims'])}, "
                  f"technical_finish_retries: {state['technical_finish_retries']})")
        return answer

    def finalize_with_accepted(outcome: str, turns_charged: int) -> str:
        result = tools.finalize_answer(state["accepted_claims"], state["rejected_claims"], question)
        if result.get("ok"):
            return finish_run(result["answer_text"], outcome, turns_charged)
        return finish_run(f"INSUFFICIENT CONTEXT ({result.get('error', 'finalize failed')})",
                           "finalize_error", turns_charged)

    step = 0
    turns_used = 0  # what actually counts against the dynamic cap -- free technical
                     # finish retries (below) advance `step` (for trace numbering and
                     # the absolute safety backstop) but not this counter.
    while True:
        step += 1
        cap = _effective_max_turns(sources_touched)
        if turns_used >= cap:
            break
        if step > cap + MAX_TECHNICAL_FINISH_RETRIES + 2:  # absolute safety backstop
            break

        out = chat(msgs, cache=True)
        act = _extract_json(out)

        if verbose:
            print(f"── step {step} (turns_used {turns_used}/{cap}): chose {act.get('tool')} "
                  f"{({k: v for k, v in act.items() if k not in ('tool', 'answer')})}")

        if act.get("tool") == "read_source":
            name = act.get("name", "")
            if name:
                sources_touched.add(_source_key(name))

        if act.get("tool") == "finish":
            claims = act.get("claims") or []
            answer_field = (act.get("answer") or "").strip().upper()

            for c in claims:
                sid = c.get("source_id", "")
                if sid:
                    sources_touched.add(_source_key(sid))

            if answer_field == "INSUFFICIENT CONTEXT" and not claims and not state["accepted_claims"]:
                trace.append({
                    "step": step, "tool": "finish", "args": {"answer": answer_field, "claims": claims},
                    "outcome": "accepted_insufficient_context",
                })
                turns_used += 1
                return finish_run("INSUFFICIENT CONTEXT", "insufficient_context_direct", turns_used)

            if claims:
                errors = _check_claims(claims, state)
            elif state["accepted_claims"]:
                errors = []  # no new claims submitted, but something is already locked in -> wrap up
            else:
                errors = [{"reason": ("Provide at least one claim (source_id, quote, statement), "
                                       "or answer INSUFFICIENT CONTEXT if no source supports any claim.")}]

            if not errors:
                trace.append({
                    "step": step, "tool": "finish", "args": {"claims": claims},
                    "outcome": "accepted",
                    "accepted_claims_total": len(state["accepted_claims"]),
                })
                turns_used += 1
                return finalize_with_accepted("success", turns_used)

            # Only skip the rejection budget when EVERY error this attempt is
            # purely technical. If even one claim failed for a real reason
            # (bad verbatim match or a genuine evaluator REJECT), that must
            # still count — a technical hiccup on a DIFFERENT claim in the
            # same attempt shouldn't give a real content problem a free pass.
            is_technical = errors and all(e.get("technical_error") for e in errors)

            # A purely-technical failure gets a small, separately-capped pool of free
            # retries (doesn't cost a turn from the exploration budget, mirroring how
            # it already doesn't cost a rejection from the content budget) -- unless
            # that pool is exhausted, in which case it's charged like anything else,
            # so a genuinely broken evaluator still can't stall the run forever.
            technical_retry_available = is_technical and (
                state["technical_finish_retries"] < MAX_TECHNICAL_FINISH_RETRIES
            )
            if technical_retry_available:
                state["technical_finish_retries"] += 1
            else:
                turns_used += 1
                if not is_technical:
                    state["eval_rejections"] += 1

            trace.append({
                "step": step, "tool": "finish", "args": {"claims": claims},
                "outcome": "technical_retry_free" if technical_retry_available else
                           ("technical_retry_charged" if is_technical else "rejected"),
                "errors": errors,
                "rejections_used": state["eval_rejections"],
                "technical_finish_retries_used": state["technical_finish_retries"],
                "accepted_claims_so_far": len(state["accepted_claims"]),
            })
            if verbose:
                if technical_retry_available:
                    label = "finish hit a technical error (free retry, no turn/budget cost)"
                elif is_technical:
                    label = "finish hit a technical error (free retries exhausted, turn charged)"
                else:
                    label = "finish rejected"
                print(f"          -> {label}: {errors}")

            if (not is_technical) and state["eval_rejections"] >= MAX_EVAL_REJECTIONS:
                if state["accepted_claims"]:
                    return finalize_with_accepted("success_partial_budget_exhausted", turns_used)
                return finish_run(
                    "INSUFFICIENT CONTEXT (evaluator rejection budget exhausted)",
                    "budget_exhausted", turns_used,
                )

            failing_keys = {(e.get("source_id"), e.get("quote")) for e in errors}
            newly_locked = [
                {"source_id": c.get("source_id", ""), "quote": c.get("quote", "")}
                for c in claims
                if (c.get("source_id", ""), c.get("quote", "")) not in failing_keys
            ]
            obs = json.dumps({
                "ok": False,
                "stage": "finish_verification",
                "errors": errors,
                "newly_locked_in": newly_locked,
                "total_claims_locked_in_so_far": len(state["accepted_claims"]),
                "note": ("Locked-in claims are final — do not resend or re-verify them. Fix ONLY "
                         "the claims in 'errors', or call finish with no new claims to stop here "
                         "and use whatever is already locked in."),
                "technical_error": is_technical,
                "rejections_used": state["eval_rejections"],
                "budget": MAX_EVAL_REJECTIONS,
            })
            msgs += [
                {"role": "assistant", "content": out},
                {"role": "user", "content": "OBSERVATION:\n" + obs},
            ]
            continue

        obs = run_tool(act)
        turns_used += 1
        trace.append({
            "step": step,
            "tool": act.get("tool"),
            "args": {k: v for k, v in act.items() if k != "tool"},
            "result": _truncate(json.loads(obs)) if obs.strip().startswith(("{", "[")) else _truncate(obs),
        })
        if verbose:
            print(f"          -> {obs[:200]}")

        msgs += [
            {"role": "assistant", "content": out},
            {"role": "user", "content": "OBSERVATION:\n" + obs},
        ]

    if state["accepted_claims"]:
        return finalize_with_accepted("success_partial_turn_limit", turns_used)
    return finish_run(
        "INSUFFICIENT CONTEXT (turn limit reached without finishing)",
        "turn_limit", turns_used,
    )
