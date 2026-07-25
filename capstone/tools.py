"""Tools for the Literature Review Assistant capstone."""

import json
import re
import hashlib
from pathlib import Path
from pypdf import PdfReader

BASE_DIR = Path(__file__).parent
SOURCES_JSON = BASE_DIR / "sources.json"
SOURCES_DIR = BASE_DIR / "sources"
ANSWERS_DIR = BASE_DIR / "answers"

_TEXT_CACHE: dict[str, str] = {}

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
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "text": text}


def search_sources(query: str) -> list[dict]:
    query_lower = query.lower()
    hits = []
    for path in sorted(SOURCES_DIR.iterdir()):
        if not path.is_file():
            continue
        try:
            text = _get_text_by_filename(path.name)
        except FileNotFoundError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line and query_lower in line.lower():
                hits.append({"file": path.name, "line": line})
    return hits


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

    if _normalize(quote) not in _normalize(source_text):
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
