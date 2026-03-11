"""
shared.py  —  Common utilities for the abstract-processing pipeline.

Imported by 1_extract.py and 2_review_gui.py.
Has no side-effects when imported (safe to do so from the GUI).

Run as a script for one-time data migration:
    py scripts/pipeline/shared.py --migrate
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT     = Path(__file__).resolve().parents[2]
ABSTRACTS_DIR = REPO_ROOT / "data" / "abstracts"
METADATA_PATH = REPO_ROOT / "data" / "abstract_metadata.json"
STAGING_PATH  = REPO_ROOT / "data" / "staging.json"
REGISTRY_PATH = REPO_ROOT / "data" / "affiliation_registry.json"

# Legacy paths (used only during migration)
_LEGACY_METADATA = REPO_ROOT / "data" / "intermediate" / \
    "metadata_output_20251023_1016_cleaned_affiliations3.json"
_LEGACY_REGISTRY = REPO_ROOT / "data" / "intermediate" / "affiliation_groups3.json"

# ── Per-conference constants (pre-filled, never extracted) ────────────────────
BATCH_DEFAULTS: dict[str, str] = {
    "dct:publisher": "DECHEMA",
    "dcat:theme":    "http://eurovoc.europa.eu/100142",
    "dct:type":      "http://purl.org/spar/fabio/Abstract",
    "dct:language":  "en",
}

# Affiliation matching thresholds
AFF_HI = 0.95   # ≥ this → auto-select "existing"
AFF_LO = 0.70   # < this → auto-select "new"


# ── JSON I/O ──────────────────────────────────────────────────────────────────

def load_json(path: Path | str) -> list[dict]:
    """Load a JSON array from *path*.  Returns [] if the file does not exist."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_json(data: list[dict] | dict, path: Path | str) -> None:
    """Atomically write *data* as pretty-printed JSON to *path*."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    shutil.move(str(tmp), str(p))


def strip_cr(path: Path | str) -> None:
    """Remove Windows \\r characters that rdflib may introduce on serialisation."""
    p = Path(path)
    with open(p, "rb") as f:
        data = f.read()
    cleaned = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if cleaned != data:
        with open(p, "wb") as f:
            f.write(cleaned)


# ── Affiliation registry ──────────────────────────────────────────────────────

def load_registry() -> dict[str, list[str]]:
    """Load affiliation_registry.json → {canonical: [variant, ...]}."""
    p = REGISTRY_PATH
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: dict[str, list[str]]) -> None:
    """Save affiliation registry (sorted by canonical for readability)."""
    sorted_reg = dict(sorted(registry.items()))
    save_json(sorted_reg, REGISTRY_PATH)


def registry_add_variant(registry: dict[str, list[str]],
                          canonical: str, variant: str) -> None:
    """Add *variant* to *canonical*'s variant list if not already present."""
    if variant == canonical:
        return
    variants = registry.setdefault(canonical, [])
    if variant not in variants:
        variants.append(variant)


def registry_add_canonical(registry: dict[str, list[str]],
                            canonical: str, first_variant: str | None = None) -> None:
    """Register a brand-new canonical (optionally with its first raw variant)."""
    if canonical not in registry:
        registry[canonical] = []
    if first_variant and first_variant != canonical:
        registry_add_variant(registry, canonical, first_variant)


def migrate_old_registry(groups3_path: Path) -> dict[str, list[str]]:
    """
    Convert affiliation_groups3.json  {canonical: [{variant: count}, ...]}
    to the new format                 {canonical: [variant, ...]}
    (canonical itself is excluded from the variant list).
    """
    with open(groups3_path, encoding="utf-8") as f:
        old: dict[str, list[dict]] = json.load(f)

    new: dict[str, list[str]] = {}
    for canonical, variant_list in old.items():
        variants: list[str] = []
        for vdict in variant_list:
            for v in vdict:
                if v != canonical:
                    variants.append(v)
        new[canonical] = variants
    return new


# ── Affiliation matching ──────────────────────────────────────────────────────

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_affiliation(
    raw: str,
    registry: dict[str, list[str]],
    hi: float = AFF_HI,
    lo: float = AFF_LO,
) -> tuple[str | None, float, str]:
    """
    Fuzzy-match *raw* against every canonical and all its variants.

    Returns (best_canonical_or_None, best_score, decision) where decision is one of:
      "auto_existing"  — score >= hi   → pre-select "Map to existing"
      "auto_new"       — score <  lo   → pre-select "Add as new"
      "pending"        — lo <= score < hi → neither pre-selected
    """
    best_score = 0.0
    best_canonical: str | None = None

    for canonical, variants in registry.items():
        # Score against canonical itself
        s = _sim(raw, canonical)
        if s > best_score:
            best_score = s
            best_canonical = canonical
        # Score against each known variant
        for v in variants:
            s = _sim(raw, v)
            if s > best_score:
                best_score = s
                best_canonical = canonical   # variant → maps to its canonical

    if best_score >= hi:
        decision = "auto_existing"
    elif best_score < lo:
        decision = "auto_new"
        best_canonical = None   # caller should use raw as the default new canonical
    else:
        decision = "pending"

    return best_canonical, best_score, decision


def build_aff_decisions(
    authors: list[dict],
    registry: dict[str, list[str]],
) -> list[dict]:
    """
    Return a list of _aff_decision records (one per author × affiliation).
    Each record has: author, raw, matched_canonical, match_score, decision.
    """
    decisions: list[dict] = []
    for author in authors:
        name = author.get("name", "")
        for raw_aff in author.get("affiliations", []):
            canonical, score, decision = match_affiliation(raw_aff, registry)
            decisions.append({
                "author":            name,
                "raw":               raw_aff,
                "matched_canonical": canonical,
                "match_score":       round(score, 4),
                "decision":          decision,
            })
    return decisions


def apply_aff_decisions(entry: dict) -> dict:
    """
    Given a staged entry whose _aff_decisions have all been finalised, replace
    each author's affiliations with the decided canonical (or new canonical).

    Returns a *copy* of the entry without the staging-only _* fields.
    """
    out = copy.deepcopy(entry)

    # Build a lookup: (author_name, raw_aff) → chosen_canonical
    chosen: dict[tuple[str, str], str] = {}
    for dec in out.get("_aff_decisions", []):
        key = (dec["author"], dec["raw"])
        if dec["decision"] in ("auto_existing", "existing"):
            chosen[key] = dec["matched_canonical"] or dec["raw"]
        elif dec["decision"] in ("auto_new", "new"):
            # "new_canonical" set by the GUI when the user typed a name
            chosen[key] = dec.get("new_canonical") or dec["raw"]
        else:
            chosen[key] = dec["raw"]   # fallback: keep raw

    # Replace affiliations in authors list
    for author in out.get("authors", []):
        name = author.get("name", "")
        author["affiliations"] = [
            chosen.get((name, aff), aff)
            for aff in author.get("affiliations", [])
        ]

    # Strip staging-only fields
    for key in ("_status", "_aff_decisions", "_raw_affiliations"):
        out.pop(key, None)

    return out


# ── Deduplication ─────────────────────────────────────────────────────────────

def is_duplicate(file_title: str, title: str) -> bool:
    """Return True if file_title or (normalised) title already exists."""
    def _norm(s: str) -> str:
        return s.strip().lower()

    for store in (METADATA_PATH, STAGING_PATH):
        for entry in load_json(store):
            if entry.get("file_title", "") == file_title:
                return True
            if _norm(entry.get("dct:title", "")) == _norm(title) and title:
                return True
    return False


# ── Abstract metadata helpers ─────────────────────────────────────────────────

def all_file_titles() -> list[str]:
    """Return file_title values from both metadata and staging."""
    titles = []
    for store in (METADATA_PATH, STAGING_PATH):
        for entry in load_json(store):
            ft = entry.get("file_title")
            if ft:
                titles.append(ft)
    return titles


def pdf_path_for(file_title: str) -> Path | None:
    """Resolve the PDF path for a given file_title. Returns None if not found."""
    p = ABSTRACTS_DIR / f"{file_title}.pdf"
    return p if p.exists() else None


# ── Data migration (run once) ─────────────────────────────────────────────────

def _run_migration() -> None:
    """Copy legacy data files to the new layout and convert the registry format."""
    print("=== Migration ===")

    # 1. abstract_metadata.json
    if METADATA_PATH.exists():
        print(f"  SKIP  abstract_metadata.json already exists")
    elif _LEGACY_METADATA.exists():
        shutil.copy2(_LEGACY_METADATA, METADATA_PATH)
        print(f"  OK    {_LEGACY_METADATA.name} → abstract_metadata.json")
    else:
        save_json([], METADATA_PATH)
        print(f"  INIT  abstract_metadata.json created (empty)")

    # 2. staging.json
    if STAGING_PATH.exists():
        print(f"  SKIP  staging.json already exists")
    else:
        save_json([], STAGING_PATH)
        print(f"  INIT  staging.json created (empty)")

    # 3. affiliation_registry.json
    if REGISTRY_PATH.exists():
        print(f"  SKIP  affiliation_registry.json already exists")
    elif _LEGACY_REGISTRY.exists():
        new_reg = migrate_old_registry(_LEGACY_REGISTRY)
        save_registry(new_reg)
        print(f"  OK    {_LEGACY_REGISTRY.name} → affiliation_registry.json"
              f" ({len(new_reg)} canonicals)")
    else:
        save_registry({})
        print(f"  INIT  affiliation_registry.json created (empty)")

    print("Migration complete.")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Pipeline shared utilities / migration")
    parser.add_argument("--migrate", action="store_true",
                        help="Run one-time data migration from legacy layout")
    args = parser.parse_args()

    if args.migrate:
        _run_migration()
    else:
        parser.print_help()
