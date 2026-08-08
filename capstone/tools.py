"""Tools for the Literature Review Assistant capstone."""

import json
import re
import unicodedata
import hashlib
from pathlib import Path
from pypdf import PdfReader

BASE_DIR = Path(__file__).parent
SOURCES_JSON = BASE_DIR / "sources.json"
SOURCES_DIR = BASE_DIR / "sources"
ANSWERS_DIR = BASE_DIR / "answers"

_TEXT_CACHE: dict[str, str] = {}

SEARCH_MAX_HITS = 20  # canonical matching hits far more often than the old per-line
    # search, so an uncapped result set could flood the agent's context.
SEARCH_SNIPPET_CHARS = 320  # ceiling on one returned snippet, comfortably above the
    # ~200-char guidance the agent gets for a single quote.
TERMS_WINDOW_SENTENCES = 3  # adjacent sentences an all-terms match may span; 3 covers the
    # common "caption names it, next sentence measures it" pattern without letting a
    # match drift so far apart that the passage no longer reads as one statement.
SNIPPET_LEAD_CHARS = 60  # context kept BEFORE an over-long match; small on purpose so
    # the rest of the matched sentence survives the clamp (see _snippet).
CANDIDATE_SOURCES_MAX = 3  # stage-3 discovery is advisory, not a result set to page
    # through -- capping it keeps the observation small and keeps the signal to
    # "here's where to look," not "here's a ranked corpus browse."

_LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
}


def _load_sources() -> list[dict]:
    with open(SOURCES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_entry(source_id: str) -> dict | None:
    for entry in _load_sources():
        if entry.get("source_id") == source_id:
            return entry
    return None


def _find_entry_by_filename(filename: str) -> dict | None:
    for entry in _load_sources():
        if entry.get("filename") == filename:
            return entry
    return None


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _get_text_by_filename(filename: str) -> str:
    if filename not in _TEXT_CACHE:
        path = SOURCES_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Source file not found on disk: {path}")
        _TEXT_CACHE[filename] = _extract_pdf_text(path)
    return _TEXT_CACHE[filename]


def _read_source_text(entry: dict) -> str:
    return _get_text_by_filename(entry["filename"])


def _normalize(text: str) -> str:
    for lig, expansion in _LIGATURES.items():
        text = text.replace(lig, expansion)
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"\s*-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _canon(text: str) -> str:
    """
    Canonical form for comparison: Unicode-folded, then stripped of every
    whitespace and dash character, and lowercased.

    PDF text extraction corrupts word spacing in both directions, and neither
    direction is a property of the document -- both are noise from a lossy
    process. Measured across the five capstone sources, roughly 8% of
    quotable sentences carry at least one such corruption (13% in the worst
    source). Three forms have been observed in real runs:

        "highlight t hat"  a spurious space injected inside a word
        "wereﬁltered"      a space lost where a ligature met a word boundary
        "multiagent"       a hyphen lost when a word was split over two lines

    Comparing on raw extracted spacing means the reader who quotes what the
    sentence actually says is REJECTED, while only a reader who reproduces
    the corruption is accepted -- exactly backwards, and the direct cause of
    a real run failing on a correct quote.

    NFKC folding and the broad dash class matter for a second reason: the
    same PDF extracted by different pypdf versions does not yield identical
    text (two environments differed by 61 characters on one source here), and
    the differences are exactly these -- ligature spellings, dash variants,
    exotic space characters. Folding them means a quote verified in one
    environment still verifies in another, instead of the check depending on
    which library happened to read the file.

    None of this weakens what the check is for: the words themselves, in
    order, must still be present. A paraphrase, an altered number, an
    inserted negation or an invented sentence all still fail.
    """
    folded = unicodedata.normalize("NFKC", _normalize(text))
    out = []
    for ch in folded:
        if ch.isspace() or unicodedata.category(ch) in ("Pd", "Cf"):
            continue  # Pd = every dash/hyphen variant; Cf = soft hyphen and friends
        out.append(ch)
    return "".join(out).lower()


def _canon_with_map(text: str) -> tuple[str, list[int]]:
    """
    Canonical form plus, for each canonical character, its index in the
    normalized text -- so a match found in canonical space can be reported
    back as a real, quotable span of the original.

    NFKC can map one character to several (the ﬁ ligature becomes two), so
    each produced character points back at the single source character it
    came from; a span reconstructed from those indices still covers the
    original text exactly.
    """
    norm = _normalize(text)
    chars: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(norm):
        for sub in unicodedata.normalize("NFKC", ch):
            if sub.isspace() or unicodedata.category(sub) in ("Pd", "Cf"):
                continue
            chars.append(sub.lower())
            idx.append(i)
    return "".join(chars), idx


def _format_in_text_citation(entry: dict) -> str:
    authors = entry.get("author", [])
    year = entry.get("issued", {}).get("date-parts", [[None]])[0][0]
    if not authors:
        return f"(Unknown, {year})"
    if len(authors) == 1:
        return f"({authors[0]['family']}, {year})"
    if len(authors) == 2:
        return f"({authors[0]['family']} & {authors[1]['family']}, {year})"
    return f"({authors[0]['family']} et al., {year})"


def _format_reference_entry(entry: dict) -> str:
    authors = entry.get("author", [])
    author_str = ", ".join(
        f"{a['family']}, {a['given'][0]}." for a in authors
    ) if authors else "Unknown"
    year = entry.get("issued", {}).get("date-parts", [[None]])[0][0]
    title = entry.get("title", "Untitled")
    container = entry.get("container-title", "")
    volume = entry.get("volume", "")
    issue = entry.get("issue", "")
    page = entry.get("page", "")
    doi = entry.get("DOI", "")

    ref = f"{author_str} ({year}). {title}."
    if container:
        ref += f" {container}"
        if volume:
            ref += f", {volume}"
        if issue:
            ref += f"({issue})"
        if page:
            ref += f", {page}"
        ref += "."
    if doi:
        ref += f" https://doi.org/{doi}"
    return ref


def get_citation(source_id: str) -> dict | None:
    entry = _find_entry(source_id)
    if entry is None:
        return None
    return {
        "in_text": _format_in_text_citation(entry),
        "reference": _format_reference_entry(entry),
    }


def list_sources() -> list[dict]:
    results = []
    for path in sorted(SOURCES_DIR.iterdir()):
        if not path.is_file():
            continue
        entry = _find_entry_by_filename(path.name)
        results.append({
            "file": path.name,
            "id": entry.get("source_id") if entry else None,
        })
    return results


def lookup_citation(source_id: str) -> dict:
    citation = get_citation(source_id)
    if citation is None:
        return {"ok": False, "error": f"Unknown source_id: {source_id!r} not found in sources.json"}
    return {"ok": True, "in_text": citation["in_text"], "reference": citation["reference"]}


def read_source(name: str) -> dict:
    try:
        text = _get_text_by_filename(name)
    except FileNotFoundError:
        # List what IS available. A real run invented a filename that looked
        # plausible ("Zhang2025.pdf"), got back only "not found", and spent
        # further turns re-listing and guessing. The error can answer the
        # question it provokes.
        available = [p.name for p in sorted(SOURCES_DIR.iterdir()) if p.is_file()]
        return {"ok": False,
                "error": f"No source named {name!r}. Available sources: {', '.join(available)}"}
    return {"ok": True, "text": text}


def search_sources(query: str, max_hits: int = SEARCH_MAX_HITS) -> dict:
    """
    Three-stage search over every source.

    Stage 1 "phrase": the whole query as one contiguous span.
    Stage 2 "terms":  only if stage 1 found nothing -- sentences containing
                      ALL the query's words, in any order.
    Stage 3 "candidates" (advisory only): only if stages 1 and 2 both found
                      nothing -- sources ranked by how many of the query's
                      content words appear ANYWHERE in them, even scattered
                      across unrelated sentences.

    Stage 2 exists because a model asking about several things at once writes
    a multi-concept query ("OpenManus MedAgentsBench accuracy") and expects
    keyword-search behaviour, while a bare substring search answers a
    different question -- does this exact string occur? -- and returns
    nothing even when one sentence covers all three terms. A real run issued
    that identical query three times and never recovered. Matching what the
    caller means removes the mismatch instead of documenting around it.

    Stage 3 exists for a narrower, harder case stages 1-2 cannot touch at
    all: the user's words and the source's words for the same concept don't
    overlap enough to ever land in one sentence -- "cost to operate the
    model" against a source that only ever says "computational resources"
    and "GPU utilization". No amount of query rephrasing finds that with
    substring matching, because the words genuinely differ. Stage 3 does NOT
    attempt to solve this by matching meaning -- that would mean embeddings,
    which is out of scope here. It solves a narrower, honest version of the
    problem: point at sources worth reading, using only evidence already in
    hand (word overlap), without ever claiming those sources contain the
    answer. That claim is left entirely to read_source, verify_quote, and
    the evaluator, exactly as before. Ranked by matched-term count so the
    most promising candidate sorts first; a source matching zero content
    words is not a candidate at all, so a query with no real vocabulary
    overlap anywhere in the corpus still correctly reports nothing.

    All stages compare canonical text (see _canon), so extraction artifacts
    in spacing or hyphenation cannot hide a passage that is really there.
    Every returned snippet is a real span of the source and will pass
    verify_quote as-is.
    """
    q_canon = _canon(query)
    if not q_canon:
        return {"ok": False, "error": "Empty query."}

    hits, total = _search_phrase(q_canon, max_hits)
    mode = "phrase"

    if not hits:
        terms = _query_terms(query)
        if len(terms) > 1:
            hits, total = _search_terms(terms, max_hits)
            mode = "terms"

    result = {"ok": True, "hits": hits, "total_hits": total, "match_mode": mode}
    if mode == "terms" and hits:
        result["note"] = ("No passage contained that exact phrase, so these are "
                          "sentences containing all of its words instead.")
    if total > len(hits):
        result["truncated"] = True

    if not hits:
        terms = _query_terms(query)
        candidates = _rank_candidate_sources(terms) if terms else []
        if candidates:
            result["candidate_sources"] = candidates
            result["note"] = (
                "No exact or combined match, but these sources share some "
                "vocabulary with your query, ranked by how many query words "
                "each contains. This is NOT evidence they answer the "
                "question -- only that they may be worth reading directly "
                "with read_source instead of trying more keyword variations.")

    return result


def _rank_candidate_sources(terms: list[str]) -> list[dict]:
    """
    Sources ranked by how many distinct query terms occur anywhere in them.

    Deliberately the crudest possible signal -- raw vocabulary overlap, no
    weighting, no proximity, no meaning. That crudeness is the point: it is
    fully deterministic, needs no model call and no index beyond the text
    already read for search itself, and it degrades honestly. A source that
    shares zero terms is never listed, so a query whose vocabulary is truly
    absent from the whole corpus still correctly yields no candidates rather
    than a plausible-looking guess.
    """
    scored = []
    for name, text in _iter_sources():
        canon = _canon(text)
        matched = [t for t in terms if t in canon]
        if matched:
            scored.append({"file": name, "matched_terms": matched, "score": len(matched)})
    scored.sort(key=lambda c: c["score"], reverse=True)
    for c in scored:
        del c["score"]  # matched_terms already conveys it; keep the field list minimal
    return scored[:CANDIDATE_SOURCES_MAX]


_STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "into",
              "versus", "vs", "between", "their", "its", "did", "does", "how",
              "what", "which", "any", "are", "was", "were", "have", "has"}


def _query_terms(query: str) -> list[str]:
    """
    Content words of a query, for the all-terms fallback.

    Split on hyphens as well as whitespace: canonicalisation strips hyphens,
    so "symbolic-vs-neural" would otherwise collapse into the single
    unsearchable token "symbolicvsneural". Connectives are dropped because
    they carry no locating power and, matched as substrings, would hit
    inside unrelated words.
    """
    raw = re.split(r"[\s\-/]+", query.lower())
    out = []
    for tok in raw:
        t = _canon(tok)
        if len(t) >= 3 and t not in _STOPWORDS:
            out.append(t)
    return out


def _iter_sources():
    for path in sorted(SOURCES_DIR.iterdir()):
        if not path.is_file():
            continue
        try:
            yield path.name, _get_text_by_filename(path.name)
        except FileNotFoundError:
            continue


def _search_phrase(q_canon: str, max_hits: int) -> tuple[list[dict], int]:
    hits: list[dict] = []
    total = 0
    for name, text in _iter_sources():
        canon, idx = _canon_with_map(text)
        norm = _normalize(text)
        start = 0
        while True:
            i = canon.find(q_canon, start)
            if i == -1:
                break
            total += 1
            start = i + max(1, len(q_canon))
            if len(hits) < max_hits:
                at = idx[i]
                end = idx[min(i + len(q_canon), len(idx)) - 1] + 1
                hits.append({"file": name, "line": _snippet(norm, at, end - at)})
    return hits, total


def _search_terms(terms: list[str], max_hits: int) -> tuple[list[dict], int]:
    """
    Passages containing all the terms, searched over a short sliding window of
    ADJACENT sentences rather than one sentence at a time.

    Requiring every term inside a single sentence sounds strict-but-safe and
    is neither: prose routinely spreads one fact across neighbours, and figure
    captions almost always do. A real run asked for OpenManus / overall /
    accuracy / MedAgentsBench and got nothing, because the caption names the
    benchmark in one sentence and reports the number in the next. The passage
    was there; the sentence boundary hid it.

    The window is capped at SEARCH_SNIPPET_CHARS so a returned span stays
    quotable, and joining consecutive sentences with a single space
    reconstructs the normalized text exactly -- _split_sentences consumes that
    separating space -- so the span really is a contiguous substring and
    passes verify_quote as-is.
    """
    hits: list[dict] = []
    total = 0
    for name, text in _iter_sources():
        norm = _normalize(text)
        sents = _split_sentences(norm)
        i = 0
        while i < len(sents):
            step = 1
            for w in range(1, TERMS_WINDOW_SENTENCES + 1):
                if i + w > len(sents):
                    break
                span = " ".join(sents[i:i + w]).strip()
                if len(span) > SEARCH_SNIPPET_CHARS:
                    break
                if all(t in _canon(span) for t in terms):
                    total += 1
                    if len(hits) < max_hits:
                        hits.append({"file": name, "line": span})
                    step = w  # don't re-report the same passage from inside itself
                    break
            i += step
    return hits, total


def _split_sentences(norm: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.]) ", norm) if s.strip()]


def _snippet(norm: str, at: int, length: int) -> str:
    """
    Expands a match to its surrounding sentence, clamped to SEARCH_SNIPPET_CHARS.

    The result is always a contiguous span of the normalized text, so quoting
    it as-is passes verify_quote. No ellipsis is added, since a marker absent
    from the source would break the quote. When the sentence is too long to
    return whole the window is biased FORWARD from the match: sentence
    detection keys on ". ", which tables and captions lack, so a match just
    after a table would otherwise drag in stray cell values and lose the tail
    of its own sentence -- and the tail is usually where the substance is.
    """
    left = norm.rfind(". ", 0, at)
    left = 0 if left == -1 else left + 2
    right = norm.find(". ", at + length)
    right = len(norm) if right == -1 else right + 1

    if right - left > SEARCH_SNIPPET_CHARS:
        left = max(left, at - SNIPPET_LEAD_CHARS)
        right = min(right, left + SEARCH_SNIPPET_CHARS)
        sp = norm.find(" ", left, left + 25)
        if sp != -1 and sp < at:
            left = sp + 1
        sp = norm.rfind(" ", right - 25, right)
        if sp != -1 and sp > at + length:
            right = sp
    return norm[left:right].strip()


def _answer_file_path(answer_text: str) -> Path:
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    slug = hashlib.sha1(answer_text.encode("utf-8")).hexdigest()[:10]
    return ANSWERS_DIR / f"answer_{slug}.md"


def verify_quote(source_id: str, quote: str) -> dict:
    entry = _find_entry(source_id)
    if entry is None:
        return {"ok": False, "error": f"Unknown source_id: {source_id!r} not found in sources.json"}

    try:
        source_text = _read_source_text(entry)
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}

    if _canon(quote) not in _canon(source_text):
        return {"ok": False, "error": "Quote not found verbatim in source (after normalization)."}

    return {"ok": True}


def finalize_answer(accepted_claims: list[dict], rejected_claims: list[dict] | None = None,
                     question: str | None = None) -> dict:
    """
    accepted_claims: [{"source_id", "quote", "statement"}, ...] — each one
        already independently verified (verbatim + evaluator) before this is
        called. Each becomes its own section, tied only to its own source,
        so a rejected claim elsewhere can never blend into an accepted one.
    rejected_claims: [{"source_id", "quote", "statement", "reason"}, ...] —
        optional, purely informational; recorded in its own section, never
        contributes to the returned answer_text.
    question: the original question, printed verbatim at the top of the
        file for context. Optional so existing callers/tests don't break.
    Returns {"ok": True, "path", "answer_text"} or {"ok": False, "error"}.
    """
    if not accepted_claims:
        return {"ok": False, "error": "No accepted claims to finalize."}

    sections = []
    seen_refs = {}
    statements = []
    for claim in accepted_claims:
        source_id = claim.get("source_id", "")
        quote = claim.get("quote", "")
        statement = claim.get("statement", "")
        citation = get_citation(source_id)
        if citation is None:
            return {"ok": False, "error": f"Unknown source_id: {source_id!r} not found in sources.json"}
        sections.append(f'## {citation["in_text"]}\n\n{statement}\n\n> {quote}')
        seen_refs[citation["reference"]] = True
        statements.append(statement)

    body_parts = []
    if question:
        body_parts.append(f"# Question\n\n{question}")
    body_parts.append("# Answer")
    body_parts += sections

    if rejected_claims:
        lines = [
            f'- {r.get("source_id", "unknown")}: "{r.get("statement", "")}" — not included ({r.get("reason", "rejected")})'
            for r in rejected_claims
        ]
        body_parts.append("## Not Included (tried, but not verified)\n\n" + "\n".join(lines))

    reference_block = "\n".join(f"- {r}" for r in sorted(seen_refs))
    body_parts.append(f"## References\n\n{reference_block}")

    body = "\n\n".join(body_parts) + "\n"
    answer_text = " ".join(statements)

    path = _answer_file_path(answer_text)
    path.write_text(body, encoding="utf-8")
    return {"ok": True, "path": str(path), "answer_text": answer_text}
