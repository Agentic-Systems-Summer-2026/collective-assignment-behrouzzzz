

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
 
 
def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
 
 
def _read_source_text(entry: dict) -> str:
    filename = entry["filename"]
    if filename not in _TEXT_CACHE:
        path = SOURCES_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Source file not found on disk: {path}")
        _TEXT_CACHE[filename] = _extract_pdf_text(path)
    return _TEXT_CACHE[filename]
 
 
def _normalize(text: str) -> str:
    """
    """
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
 
 
def _answer_file_path(answer_text: str) -> Path:
    """Same answer_text -> same file, so repeated calls for a multi-source answer accumulate citations."""
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    slug = hashlib.sha1(answer_text.encode("utf-8")).hexdigest()[:10]
    return ANSWERS_DIR / f"answer_{slug}.md"
 
 
def write_annotation(source_id: str, quote: str, answer_text: str) -> dict:
    """
    """
    entry = _find_entry(source_id)
    if entry is None:
        return {"ok": False, "error": f"Unknown source_id: {source_id!r} not found in sources.json"}
 
    try:
        source_text = _read_source_text(entry)
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
 
    if _normalize(quote) not in _normalize(source_text):
        return {"ok": False, "error": "Quote not found verbatim in source (after normalization). Not saved."}
 
    citation = get_citation(source_id)
 
    path = _answer_file_path(answer_text)
    existing_citations = {}
    if path.exists():
        old = path.read_text(encoding="utf-8")
        for line in old.splitlines():
            if line.startswith("- "):
                existing_citations[line] = True
 
    citation_line = f"- {citation['in_text']}: {citation['reference']}"
    existing_citations[citation_line] = True
 
    body = f"# Answer\n\n{answer_text}\n\n"
    body += f'## Supporting quote ({citation["in_text"]})\n\n> {quote}\n\n'
    body += "## References\n\n" + "\n".join(sorted(existing_citations.keys())) + "\n"
 
    path.write_text(body, encoding="utf-8")
    return {"ok": True, "path": str(path)}
 
 
if __name__ == "__main__":
    # demo order: 1 (accept), 6 (bad id),
    # 7 (paraphrase reject), 13 (the hyphen-bug fix, the most interesting one).
 
    print("Case 1 — real quote, should ACCEPT and save a file:")
    print(write_annotation(
        source_id="Liu2026",
        quote="consistently requiring more than tenfold the token usage and at least "
              "twice the response time compared to baseline LLMs",
        answer_text="Agent systems required over 10x the tokens and 2x the response "
                    "time of baseline LLMs across benchmarks.",
    ))
 
    print("\nCase 6 — bad source_id, should REJECT:")
    print(write_annotation(
        source_id="not_a_real_id",
        quote="anything",
        answer_text="anything",
    ))
 
    print("\nCase 7 — paraphrase (not verbatim), should REJECT:")
    print(write_annotation(
        source_id="Liu2026",
        quote="the paper says agent systems use about ten times more tokens and "
              "twice the response time than plain LLMs",
        answer_text="Case 7 paraphrase test",
    ))
 
    print("\nCase 13 — quote crosses a hyphenated line break in the PDF, should ACCEPT:")
    print(write_annotation(
        source_id="AbouAli2025",
        quote="its rapid advancement has led to a fragmented understanding, often "
              "conflating modern neural systems with outdated symbolic models",
        answer_text="Agentic AI's rapid advancement has led to a fragmented "
                    "understanding of the field, per Abou Ali et al.",
    ))