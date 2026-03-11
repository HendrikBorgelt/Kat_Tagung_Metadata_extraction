"""
1_extract.py  —  Batch PDF extraction into staging.json via Ollama.

Usage:
    py scripts/pipeline/1_extract.py [options]

Options:
    --input   PATH    Folder containing PDFs  (default: data/abstracts/)
    --model   NAME    Ollama model name        (default: llama3.2)
    --issued  DATE    dct:issued for this batch, YYYY-MM-DD  (default: today)
    --skip-existing   Skip PDFs already in abstract_metadata.json or staging.json
    --dry-run         List PDFs that would be processed without calling Ollama

The script appends new entries to data/staging.json.
Entries that cannot be extracted are saved with  _status="failed"  so the
review GUI can show them for manual completion.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import date
from pathlib import Path

# ── Add repo root to path so shared can be imported ──────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import shared

# ── Ollama interaction ────────────────────────────────────────────────────────

OLLAMA_PROMPT = """\
You are a scientific metadata extraction assistant. Extract metadata from the conference abstract below.
Return ONLY a single valid JSON object — no markdown fences, no explanation.

Required JSON structure:
{{
  "dct:title": "<full title of the abstract, exactly as written>",
  "dcat:contactPoint": "<name of the presenting/corresponding author (usually underlined, asterisk-marked, or listed first)>",
  "dcat:keyword": "<semicolon-separated keywords if a keyword section exists, else empty string>",
  "authors": [
    {{"name": "<Author Name>", "affiliations": ["<full affiliation string 1>", "<full affiliation string 2>"]}}
  ],
  "dct:relation": ["<DOI or full citation string — include all references/citations found, or empty list>"]
}}

Rules:
- List EVERY named author with ALL their affiliations exactly as written in the abstract.
- An affiliation should include department, institute, university, city, and country/Germany/etc.
- dcat:contactPoint is typically the underlined or asterisk-marked author; if unclear, use the first author.
- dct:relation: include every DOI (format: https://doi.org/...) or citation string found; empty list if none.
- Return ONLY the JSON object.

Abstract text:
{text}
"""


def _call_ollama(text: str, model: str, timeout: int = 120) -> dict:
    """
    Call the Ollama REST API and return the parsed JSON response.
    Raises RuntimeError on failure.
    """
    import urllib.request
    import urllib.error

    prompt = OLLAMA_PROMPT.format(text=text[:8000])   # cap to avoid token limits
    payload = json.dumps({
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unreachable: {exc}") from exc

    response_obj = json.loads(raw)
    llm_text: str = response_obj.get("response", "")
    return _parse_llm_json(llm_text)


def _parse_llm_json(text: str) -> dict:
    """
    Extract and parse a JSON object from *text*.
    Strips markdown fences if present, then tries json.loads.
    On failure, raises ValueError.
    """
    # Strip optional markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text.strip(), flags=re.MULTILINE)

    # Find first '{' … last '}'
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in LLM output:\n{text[:300]}")
    return json.loads(text[start:end])


# ── PDF text extraction ───────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract plain text from *pdf_path* using pymupdf (fitz).
    Returns concatenated text from all pages, separated by form-feed characters.
    """
    try:
        import fitz   # pymupdf
        doc = fitz.open(str(pdf_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\f".join(pages)
    except ImportError:
        raise RuntimeError(
            "pymupdf is not installed. Run: pip install pymupdf"
        )
    except Exception as exc:
        raise RuntimeError(f"Could not read PDF: {exc}") from exc


# ── Entry validation / repair ─────────────────────────────────────────────────

_REQUIRED_KEYS = {
    "dct:title":        str,
    "dcat:contactPoint": str,
    "dcat:keyword":     str,
    "authors":          list,
    "dct:relation":     list,
}


def _validate_and_repair(data: dict) -> dict:
    """Ensure all required keys exist and have the right types."""
    for key, expected_type in _REQUIRED_KEYS.items():
        if key not in data or not isinstance(data[key], expected_type):
            data[key] = expected_type()   # default: "" or []

    # Ensure every author has 'name' and 'affiliations'
    cleaned_authors = []
    for author in data.get("authors", []):
        if isinstance(author, str):
            author = {"name": author, "affiliations": []}
        author.setdefault("name", "")
        author.setdefault("affiliations", [])
        if not isinstance(author["affiliations"], list):
            author["affiliations"] = [str(author["affiliations"])]
        cleaned_authors.append(author)
    data["authors"] = cleaned_authors

    # dct:relation must be a list of strings
    data["dct:relation"] = [str(r) for r in data.get("dct:relation", [])]

    return data


# ── Per-PDF processing ────────────────────────────────────────────────────────

def process_pdf(
    pdf_path: Path,
    model: str,
    issued: str,
    registry: dict[str, list[str]],
    skip_existing: bool,
) -> dict | None:
    """
    Process a single PDF and return a staging entry dict, or None if skipped.
    The entry always has _status = "pending" | "failed".
    """
    file_title = pdf_path.stem

    # Deduplication check
    if skip_existing and shared.is_duplicate(file_title, ""):
        return None

    entry: dict = {
        "_status":          "pending",
        "_aff_decisions":   [],
        "_raw_affiliations": {},
        "file_title":       file_title,
        **shared.BATCH_DEFAULTS,
        "dct:issued":       issued,
        "dct:title":        "",
        "dcat:contactPoint": "",
        "dcat:keyword":     "",
        "authors":          [],
        "dct:relation":     [],
    }

    # Extract PDF text
    try:
        text = extract_pdf_text(pdf_path)
    except RuntimeError as exc:
        entry["_status"] = "failed"
        entry["_error"]  = str(exc)
        return entry

    # First Ollama call
    llm_data: dict | None = None
    for attempt in range(2):
        try:
            llm_data = _call_ollama(text, model)
            break
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            if attempt == 1:
                entry["_status"] = "failed"
                entry["_error"]  = f"Ollama extraction failed: {exc}"
                return entry

    if llm_data is None:
        entry["_status"] = "failed"
        entry["_error"]  = "No data returned from Ollama"
        return entry

    llm_data = _validate_and_repair(llm_data)

    # Merge LLM output into entry
    for key in ("dct:title", "dcat:contactPoint", "dcat:keyword", "authors", "dct:relation"):
        entry[key] = llm_data[key]

    # Back up raw affiliations before matching
    entry["_raw_affiliations"] = {
        author["name"]: list(author.get("affiliations", []))
        for author in entry["authors"]
    }

    # Affiliation matching
    entry["_aff_decisions"] = shared.build_aff_decisions(entry["authors"], registry)

    return entry


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input",  default=str(shared.ABSTRACTS_DIR),
                        help="Folder of PDFs to process")
    parser.add_argument("--model",  default="llama3.2",
                        help="Ollama model name (default: llama3.2)")
    parser.add_argument("--issued", default=date.today().isoformat(),
                        help="dct:issued date for this batch (default: today)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip PDFs already in the dataset or staging")
    parser.add_argument("--dry-run", action="store_true",
                        help="List PDFs that would be processed without calling Ollama")
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f"ERROR: input folder not found: {input_dir}")
        sys.exit(1)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {input_dir}")
        return

    print(f"Found {len(pdfs)} PDF(s) in {input_dir}")

    if args.dry_run:
        registry: dict = {}
        print("\n[DRY RUN] PDFs that would be processed:")
    else:
        registry = shared.load_registry()
        print(f"Loaded affiliation registry ({len(registry)} canonicals)\n")

    staging = shared.load_json(shared.STAGING_PATH)
    n_ok = n_skip = n_fail = 0

    for i, pdf_path in enumerate(pdfs, 1):
        file_title = pdf_path.stem
        prefix = f"[{i}/{len(pdfs)}] {file_title}"

        if args.dry_run:
            if args.skip_existing and shared.is_duplicate(file_title, ""):
                print(f"  SKIP  {file_title}")
                n_skip += 1
            else:
                print(f"  WOULD extract  {file_title}")
                n_ok += 1
            continue

        if args.skip_existing and shared.is_duplicate(file_title, ""):
            print(f"  SKIP  {prefix}")
            n_skip += 1
            continue

        print(f"  ...   {prefix}", end="", flush=True)
        try:
            entry = process_pdf(pdf_path, args.model, args.issued,
                                registry, skip_existing=False)  # already checked above
            if entry is None:
                print(f"\r  SKIP  {prefix}")
                n_skip += 1
                continue

            staging.append(entry)
            shared.save_json(staging, shared.STAGING_PATH)

            status = entry.get("_status", "pending")
            if status == "failed":
                print(f"\r  FAIL  {prefix}  —  {entry.get('_error', '')[:80]}")
                n_fail += 1
            else:
                n_aff = len(entry.get("_aff_decisions", []))
                n_pending = sum(
                    1 for d in entry["_aff_decisions"] if d["decision"] == "pending"
                )
                tag = f"({n_pending} aff. pending review)" if n_pending else "(all aff. auto-matched)"
                print(f"\r  OK    {prefix}  {tag}")
                n_ok += 1

        except Exception:
            err = traceback.format_exc().splitlines()[-1]
            entry_err = {
                "_status":    "failed",
                "_error":     err,
                "file_title": file_title,
                **shared.BATCH_DEFAULTS,
                "dct:issued": args.issued,
            }
            staging.append(entry_err)
            shared.save_json(staging, shared.STAGING_PATH)
            print(f"\r  FAIL  {prefix}  —  {err[:80]}")
            n_fail += 1

    print(f"\nDone. OK={n_ok}  SKIPPED={n_skip}  FAILED={n_fail}")
    if not args.dry_run:
        print(f"Results written to: {shared.STAGING_PATH}")


if __name__ == "__main__":
    main()
