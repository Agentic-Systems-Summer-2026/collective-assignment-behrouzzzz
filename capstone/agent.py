"""Autonomous agent loop for the Literature Review Assistant capstone."""

import json
import os
import time
import hashlib
import traceback
import uuid
from pathlib import Path

import tools
from evaluator import evaluate
from common.llm import chat, STATS

MAX_TURNS = 8  # base budget, proven sufficient for single-source questions (Case 1: 7/8)
TURNS_PER_EXTRA_SOURCE = 4  # extra allowance once a 2nd, 3rd, ... distinct source is touched
MAX_TURNS_HARD_CAP = 20  # absolute ceiling regardless of source count, so cost can't run away
MAX_EVAL_REJECTIONS = 2
MIN_EXPLORATION_BEFORE_GIVEUP = 1  # at least one real search_sources/read_source call
    # required before an INSUFFICIENT CONTEXT verdict is accepted with zero claims
    # locked in. SYSTEM_PROMPT already asks the model not to give up early, but that
    # is prose, not an enforced constraint -- nothing previously stopped a same-turn
    # give-up. Deliberately 1, not higher: this is a floor on effort, not a
    # requirement to try any particular number of phrasings, which would start
    # dictating retrieval strategy rather than just ruling out zero-effort exits.
MAX_TECHNICAL_FINISH_FAILURES = 2  # charged finish attempts that failed purely technically
    # before the run gives up on the evaluator entirely. The note sent back after the first
    # one invites exactly one resubmit, so 2 is "you tried again and it was still down".
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
    -> {"ok": true, "hits": [{"file": "...", "line": "..."}, ...],
        "total_hits": N, "match_mode": "phrase" | "terms"}
       First tries your query as one exact phrase. If nothing contains that
       phrase, it retries as separate words and returns sentences containing
       ALL of them, telling you so via "match_mode": "terms". So a query
       naming several things at once still works. Spacing and hyphens are
       ignored when matching, so a passage is found even where the PDF
       extracted it oddly. Keep queries short and distinctive (roughly 1-4
       words) — a whole sentence or a restatement of the question rarely
       matches, because the words you would use to describe an idea are
       rarely the paper\'s own words. If a search returns nothing, that text
       really is absent: change the words rather than reissuing the same
       query. Each returned "line" can be quoted verbatim as-is.

       If BOTH of the above find nothing, the result may also include
       "candidate_sources": [{"file", "matched_terms"}, ...], ranked by how
       many of your query\'s words each source contains anywhere in it. This
       is NOT evidence any of them answer the question — it only means the
       question\'s own wording may not be the source\'s wording (e.g. you
       asked about "cost" and a source only ever says "computational
       resources" or "GPU utilization"). If you see this, read_source on the
       top candidate is usually more productive than trying more synonyms.
       If "candidate_sources" is absent too, that vocabulary isn\'t in the
       corpus in any form.

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
    "that the answer isn't there. Each claim must actually answer what was "
    "asked, not just be a real, verbatim, on-topic-sounding fact from a "
    "source — a true statement about the wrong metric or the wrong aspect "
    "of the topic (e.g. citing token usage when the question asked about "
    "dollar cost) is not a valid claim, even though it is grounded. If, "
    "after investigating, no source actually answers the question, finish "
    "with exactly: INSUFFICIENT CONTEXT — do not submit a grounded-but-"
    "irrelevant claim instead. "
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


def run_tool(act: dict, seen_queries: set | None = None) -> str:
    t = act.get("tool")

    if t == "list_sources":
        return json.dumps(tools.list_sources())

    if t == "search_sources":
        query = act.get("query", "")
        key = " ".join(query.lower().split())
        if seen_queries is not None and key in seen_queries:
            return json.dumps({
                "ok": False,
                "error": f"You already searched for {query!r} in this run and it "
                         f"returned nothing. Repeating it will not help — try "
                         f"different words, or read a source directly.",
            })
        result = tools.search_sources(query)
        if seen_queries is not None and not result.get("hits"):
            seen_queries.add(key)
        return json.dumps(result)

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


def _check_claims(claims: list, state: dict, original_question: str,
                   trace_path: Path | None = None, run_id: str | None = None,
                   run_start: float | None = None, step_label: str = "claim_check") -> list:
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

    original_question is passed through to evaluate() alongside each claim's
    own statement, so the evaluator checks not just "does the quote support
    this claim" but also "is this claim actually responsive to what was
    asked" -- a real, verbatim, well-supported claim about the wrong metric
    or the wrong topic (e.g. token usage when dollar cost was asked) is
    grounded but still wrong, and only the second check catches that.

    trace_path/run_id/run_start are optional: when given, each individual
    evaluate() call is bracketed with its own start/end trace event (latency,
    accept/reject outcome), the same granularity _traced_chat gives the
    generator's own calls. Left optional, defaulting to no tracing, so any
    other caller (including existing offline tests that call this function
    directly) is unaffected.
    """
    errors = []
    for i, c in enumerate(claims):
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

        # Each claim's own "statement" is checked as the specific, narrower
        # claim, but original_question is also passed so the evaluator can
        # catch a grounded claim that answers a different question than the
        # one actually asked (see docstring above).
        eval_step = f"{step_label}_{i}_evaluator"
        if trace_path is not None:
            _trace_event(trace_path, run_id, run_start, eval_step, "start")
        t0 = time.time()
        verdict = evaluate(question=statement, quote=quote, source_id=source_id,
                            original_question=original_question)
        if trace_path is not None:
            _trace_event(
                trace_path, run_id, run_start, eval_step, "end",
                latency_s=round(time.time() - t0, 3),
                decision=("accepted" if verdict.get("ok")
                           else ("technical_error" if verdict.get("technical_error") else "rejected")),
            )
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


def _trace_path_for(run_id: str) -> Path:
    return LOG_DIR / f"{run_id}.trace.jsonl"


def _trace_event(trace_path: Path, run_id: str, run_start: float, step: str, phase: str, **extra) -> None:
    """Append one crash-safe JSON line to this run's trace file.

    Ported from the BC5 observability build challenge's `_log()` (see
    Knowledge_Base.md Section 6 for the citation). The point of this
    function, specifically, is the flush()+fsync() pair: an event is
    durable on disk before the process can crash after logging it, which
    is exactly what the previous logging design (a single summary JSON
    written only at successful completion) could not guarantee. Before
    this addition, an uncaught exception anywhere in the run left no log
    at all -- a real, documented gap, not a hypothetical one.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_id": run_id,
        "elapsed_s": round(time.time() - run_start, 3),
        "step": step,
        "phase": phase,
    }
    entry.update(extra)
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _traced_chat(trace_path: Path, run_id: str, run_start: float, step: str, msgs, **chat_kwargs):
    """Wraps a chat() call with a start event and a success/failed end event.

    Calls the module-level `chat` name (not a captured reference), so test
    stubs that monkeypatch `agent.chat` (see test_min_exploration.py and
    similar) still take effect here exactly as before -- this function adds
    tracing, it does not change what gets called. On failure, the exception
    is re-raised unchanged after being recorded; this function only
    observes, it never swallows an error the rest of the loop needs to see.
    """
    calls_before = STATS.get("calls", 0)
    tokens_before = STATS.get("tokens", 0)
    _trace_event(trace_path, run_id, run_start, step, "start")
    t0 = time.time()
    try:
        result = chat(msgs, **chat_kwargs)
        _trace_event(
            trace_path, run_id, run_start, step, "end",
            decision="success",
            latency_s=round(time.time() - t0, 3),
            calls_delta=STATS.get("calls", 0) - calls_before,
            tokens_delta=STATS.get("tokens", 0) - tokens_before,
        )
        return result
    except Exception as e:
        _trace_event(
            trace_path, run_id, run_start, step, "end",
            decision="failed",
            latency_s=round(time.time() - t0, 3),
            calls_delta=STATS.get("calls", 0) - calls_before,
            tokens_delta=STATS.get("tokens", 0) - tokens_before,
            error_type=type(e).__name__, error=str(e),
        )
        raise


def _write_log(question: str, trace: list, final_answer: str, eval_rejections: int,
                outcome: str, usage: dict, sources_touched: set, effective_max_turns: int,
                accepted_claims: list, rejected_claims: list, turns_charged: int,
                technical_finish_retries: int, run_id: str | None = None) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if run_id:
        path = LOG_DIR / f"{run_id}.json"
    else:
        # Fallback for any caller that doesn't pass run_id (keeps this
        # function usable standalone, e.g. from a REPL or a future script).
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
        "max_technical_finish_failures": MAX_TECHNICAL_FINISH_FAILURES,
        "usage": usage,
        "accepted_claims": accepted_claims,
        "rejected_claims": rejected_claims,
        "trace": trace,
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def answer_question(question: str, verbose: bool = False) -> str:
    """Public entry point -- same signature and behavior as before this
    change (same return type, same exceptions propagate to the caller, so
    run_full_revalidation.py and every existing test needs no changes).

    What is new: a run_id and trace_path are created here, in this outer
    frame, before the real work starts, so both survive even if the inner
    implementation raises partway through. This ports the BC5 observability
    build challenge's `run()` wrapper pattern (see Knowledge_Base.md Section
    6 for the citation) to close a real, documented gap: previously, an
    uncaught exception anywhere in the loop (a chat() call raising instead
    of returning, for example) meant the run ended with no log written at
    all, successful or not. Now:
      - every tool call and every model call (generator and evaluator) gets
        its own start/end trace line, written and fsynced immediately, in
        `logs/<run_id>.trace.jsonl`;
      - an uncaught exception is recorded as one "crashed" trace event, with
        the full traceback, before being re-raised unchanged -- this
        function does not swallow errors, it only guarantees one is never
        silently unlogged;
      - a "session_end" trace event is written in a finally block on every
        exit path, so a trace file that never got its closing line is
        itself a visible signal something went wrong mid-run.

    The existing per-run summary JSON (`logs/<run_id>.json`, written by
    _write_log via finish_run/finalize_with_accepted on every *successful*
    completion path) is unchanged in format and is still the primary
    evidence source for docs/cases.md and the evaluation record. The trace
    file is a new, complementary layer specifically for the failure paths
    the summary log was never able to cover.
    """
    run_id = (f"{time.strftime('%Y%m%dT%H%M%S')}_"
              f"{hashlib.sha1(question.encode('utf-8')).hexdigest()[:10]}_"
              f"{uuid.uuid4().hex[:6]}")
    trace_path = _trace_path_for(run_id)
    run_start = time.time()
    _trace_event(trace_path, run_id, run_start, "run", "start", question_chars=len(question))
    outcome = "unknown"
    try:
        result = _answer_question_impl(question, verbose, run_id, trace_path, run_start)
        outcome = "completed"
        return result
    except Exception as e:
        outcome = "crashed"
        _trace_event(
            trace_path, run_id, run_start, "run", "crashed",
            error_type=type(e).__name__, error=str(e), traceback=traceback.format_exc(),
        )
        if verbose:
            print(f"── CRASHED, recorded to {trace_path} before re-raising: {type(e).__name__}: {e}")
        raise
    finally:
        _trace_event(
            trace_path, run_id, run_start, "run", "session_end",
            outcome=outcome, total_runtime_s=round(time.time() - run_start, 3),
        )


def _answer_question_impl(question: str, verbose: bool, run_id: str, trace_path: Path, run_start: float) -> str:
    state = {
        "eval_rejections": 0,
        "verified_keys": set(),
        "rejected_keys": set(),
        "accepted_claims": [],
        "rejected_claims": [],
        "technical_finish_retries": 0,
        "technical_finish_failures": 0,
    }
    trace = []
    sources_touched = set()
    failed_queries: set[str] = set()
    exploration_attempts = 0  # total search_sources + read_source calls this run,
        # regardless of outcome -- used only to gate a premature INSUFFICIENT CONTEXT
        # (see MIN_EXPLORATION_BEFORE_GIVEUP below), never to gate a real answer
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
                           turns_charged, state["technical_finish_retries"], run_id=run_id)
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

        out = _traced_chat(trace_path, run_id, run_start, f"turn_{step}_generator", msgs, cache=True)
        act = _extract_json(out)

        if verbose:
            print(f"── step {step} (turns_used {turns_used}/{cap}): chose {act.get('tool')} "
                  f"{({k: v for k, v in act.items() if k not in ('tool', 'answer')})}")

        if act.get("tool") in ("search_sources", "read_source"):
            exploration_attempts += 1

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
                if exploration_attempts < MIN_EXPLORATION_BEFORE_GIVEUP:
                    # Nothing upstream of this ever required the model to actually
                    # look before giving up -- SYSTEM_PROMPT only asks for it in
                    # prose ("don't give up after one or two failed searches"),
                    # and that line is advisory, not enforced. Confirmed by
                    # reading the loop: this branch's condition never referenced
                    # exploration_attempts before this change, so a model could
                    # legally call finish/INSUFFICIENT CONTEXT on step 1 with zero
                    # search_sources or read_source calls and it would be accepted
                    # outright. Every real run so far happened to explore first,
                    # but "happened to" is not a guarantee this system should rely
                    # on for a verdict that gets reported as fact. This is a floor
                    # on EFFORT only (at least one real attempt to look) -- it says
                    # nothing about which words to search for, so it adds no new
                    # retrieval logic and cannot change what counts as a correct
                    # answer, only how early a negative one may be accepted.
                    trace.append({
                        "step": step, "tool": "finish",
                        "args": {"answer": answer_field, "claims": claims},
                        "outcome": "insufficient_context_rejected_no_attempt",
                    })
                    obs = json.dumps({
                        "ok": False,
                        "error": "You haven't tried search_sources or read_source yet this "
                                 "run. Look before concluding the sources don't cover this.",
                    })
                    turns_used += 1
                    msgs += [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": "OBSERVATION:\n" + obs},
                    ]
                    continue
                trace.append({
                    "step": step, "tool": "finish", "args": {"answer": answer_field, "claims": claims},
                    "outcome": "accepted_insufficient_context",
                })
                turns_used += 1
                return finish_run("INSUFFICIENT CONTEXT", "insufficient_context_direct", turns_used)

            if claims:
                errors = _check_claims(claims, state, question,
                                        trace_path=trace_path, run_id=run_id, run_start=run_start,
                                        step_label=f"turn_{step}_finish")
            elif state["accepted_claims"]:
                errors = []  # no new claims submitted, but something is already locked in -> wrap up
            else:
                errors = [{"reason": ("Provide at least one claim (source_id, quote, statement), "
                                       "or answer INSUFFICIENT CONTEXT if no source supports any claim.")}]

            # A purely-technical failure (e.g. an evaluator network timeout) has nothing
            # to do with the model's judgment -- there is no useful decision for the
            # model to make about "how do I fix a timeout," so this is retried silently
            # in-process (mirroring evaluate()'s own internal retry one level down)
            # instead of spending a model turn and hoping the model just resubmits the
            # same claim unchanged. A real run showed exactly the failure mode this
            # avoids: the model received a technical-error observation and, instead of
            # resubmitting, went back to searching for a different phrasing -- burning
            # the run's last turn on a redundant search. Bounded by the same
            # MAX_TECHNICAL_FINISH_RETRIES pool so a permanently-down evaluator still
            # can't stall the run forever; each retry re-checks only the claims that are
            # still outstanding (verified/rejected ones are cached and skipped).
            is_technical = errors and all(e.get("technical_error") for e in errors)
            while claims and is_technical and state["technical_finish_retries"] < MAX_TECHNICAL_FINISH_RETRIES:
                state["technical_finish_retries"] += 1
                if verbose:
                    print(f"          -> technical error, auto-retrying in-process "
                          f"(attempt {state['technical_finish_retries']}/{MAX_TECHNICAL_FINISH_RETRIES}), "
                          f"no turn or budget cost: {errors}")
                errors = _check_claims(claims, state, question,
                                        trace_path=trace_path, run_id=run_id, run_start=run_start,
                                        step_label=f"turn_{step}_finish_retry{state['technical_finish_retries']}")
                is_technical = errors and all(e.get("technical_error") for e in errors)

            if not errors:
                trace.append({
                    "step": step, "tool": "finish", "args": {"claims": claims},
                    "outcome": "accepted",
                    "accepted_claims_total": len(state["accepted_claims"]),
                    "technical_finish_retries_used": state["technical_finish_retries"],
                })
                turns_used += 1
                return finalize_with_accepted("success", turns_used)

            # Either a genuine content rejection, or the free technical-retry pool is
            # now exhausted -- from here on this attempt is charged normally.
            turns_used += 1
            if not is_technical:
                state["eval_rejections"] += 1

            trace.append({
                "step": step, "tool": "finish", "args": {"claims": claims},
                "outcome": "technical_retries_exhausted" if is_technical else "rejected",
                "errors": errors,
                "rejections_used": state["eval_rejections"],
                "technical_finish_retries_used": state["technical_finish_retries"],
                "accepted_claims_so_far": len(state["accepted_claims"]),
            })
            if verbose:
                label = ("finish hit a technical error (free retries exhausted, turn charged)"
                          if is_technical else "finish rejected")
                print(f"          -> {label}: {errors}")

            if is_technical:
                # The free-retry pool is spent and the evaluator is STILL failing.
                # Without a terminal condition here the run grinds on: technical
                # errors deliberately do not count against MAX_EVAL_REJECTIONS
                # (they are not the model's fault), so nothing else stops it, and
                # a real run burned four turns resubmitting a correct, already
                # quote-verified claim into a service returning 503 before
                # reporting "INSUFFICIENT CONTEXT (turn limit reached)". That
                # report is wrong and, worse, indistinguishable in the logs from
                # a genuine "no source supports this" -- a silent false negative.
                # One resubmit is allowed (the note below invites exactly one),
                # then the run ends and says what actually happened.
                state["technical_finish_failures"] += 1
                if state["technical_finish_failures"] >= MAX_TECHNICAL_FINISH_FAILURES:
                    if state["accepted_claims"]:
                        return finalize_with_accepted(
                            "success_partial_evaluator_unavailable", turns_used)
                    return finish_run(
                        "EVALUATOR UNAVAILABLE — the verification service could not be "
                        "reached, so no claim could be checked. This is an infrastructure "
                        "failure, NOT a finding that the sources lack an answer.",
                        "evaluator_unavailable", turns_used,
                    )

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
            note = ("Locked-in claims are final — do not resend or re-verify them. Fix ONLY "
                     "the claims in 'errors', or call finish with no new claims to stop here "
                     "and use whatever is already locked in.")
            if is_technical:
                note = ("This was a repeated network/infrastructure failure, not a problem "
                        "with your quote or claim — it was already retried automatically "
                        "several times. This is NOT a signal to search for a different quote "
                        "or phrasing. You may resubmit this exact same claim once more, or "
                        "call finish with no new claims to stop here and use whatever is "
                        "already locked in.")
            obs = json.dumps({
                "ok": False,
                "stage": "finish_verification",
                "errors": errors,
                "newly_locked_in": newly_locked,
                "total_claims_locked_in_so_far": len(state["accepted_claims"]),
                "note": note,
                "technical_error": is_technical,
                "rejections_used": state["eval_rejections"],
                "budget": MAX_EVAL_REJECTIONS,
            })
            msgs += [
                {"role": "assistant", "content": out},
                {"role": "user", "content": "OBSERVATION:\n" + obs},
            ]
            continue

        tool_step = f"turn_{step}_tool_{act.get('tool', 'unknown')}"
        _trace_event(trace_path, run_id, run_start, tool_step, "start")
        t0 = time.time()
        obs = run_tool(act, failed_queries)
        _trace_event(trace_path, run_id, run_start, tool_step, "end",
                     latency_s=round(time.time() - t0, 3))
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
