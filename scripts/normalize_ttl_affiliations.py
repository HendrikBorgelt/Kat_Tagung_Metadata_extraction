"""
normalize_ttl_affiliations.py
─────────────────────────────
One-time (or re-runnable) script that merges duplicate organization URIs in the
main TTL file.

Background
----------
The TTL was generated from an older (pre-normalization) version of the JSON.
Affiliation strings were later cleaned/grouped in
  data/intermediate/metadata_output_20251023_1016_cleaned_affiliations3.json
  data/intermediate/affiliation_groups3.json

Because the URI is derived deterministically from the affiliation string via
  name_to_uri(s) = re.sub(r"[^A-Za-z0-9\\s._-]","",s).replace(".","").replace(" ","_")
two strings that describe the same institution but differ in punctuation or
word order produce different URIs.  This script:

  1. Collects "canonical" affiliation strings from the cleaned JSON (ground truth).
  2. Uses affiliation_groups3.json to map known variant strings → canonical strings.
  3. Falls back to fuzzy matching (SequenceMatcher) to catch variants not covered
     by the groups file, with a configurable similarity threshold.
  4. Merges all variant org URIs into the canonical URI (rewrites every triple
     that references the old URI as subject or object).
  5. Strips Windows \\r characters introduced by rdflib's serializer.
  6. Saves the result back to the original TTL path (in-place).

Dry-run mode (default)
----------------------
Run without arguments to see what would be merged – nothing is saved.

    python scripts/normalize_ttl_affiliations.py

Apply mode
----------
    python scripts/normalize_ttl_affiliations.py --apply

Adjust similarity threshold (default 0.72):
    python scripts/normalize_ttl_affiliations.py --apply --threshold 0.8
"""

import os
import re
import sys
import json
import argparse
from difflib import SequenceMatcher
from urllib.parse import quote

from rdflib import Graph, Namespace, URIRef, Literal, RDF
from rdflib.namespace import RDFS, OWL

# ── Paths ────────────────────────────────────────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TTL_PATH    = os.path.join(_ROOT, "data", "rdf",
                           "abstracts_katalytikertagung_w_affili_w_classes.ttl")
JSON_PATH   = os.path.join(_ROOT, "data", "intermediate",
                           "metadata_output_20251023_1016_cleaned_affiliations3.json")
GROUPS_PATH = os.path.join(_ROOT, "data", "intermediate",
                           "affiliation_groups3.json")

# ── Namespaces ────────────────────────────────────────────────────────────────
EX     = Namespace("http://example.org/katalytikertagung/")
SCHEMA = Namespace("https://schema.org/")

DEFAULT_THRESHOLD = 0.72   # SequenceMatcher ratio threshold for fuzzy fallback


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def name_to_uri(name: str) -> URIRef:
    """Mirror of the function used in json_to_rdf_with_classes_0_0_0.py."""
    clean = re.sub(r"[^A-Za-z0-9\s._-]", "", name.strip()).replace(".", "").replace(" ", "_")
    return EX[quote(clean)]


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def load_canonical_affiliations(json_path: str) -> dict[str, URIRef]:
    """Return {affiliation_string: canonical_uri} from the cleaned JSON."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    canon = {}
    for entry in data:
        for author in entry.get("authors", []):
            for aff in author.get("affiliations", []):
                aff = aff.strip()
                if aff and aff not in canon:
                    canon[aff] = name_to_uri(aff)
    return canon


def load_variant_map(groups_path: str) -> dict[str, str]:
    """
    Return {variant_string: canonical_string} from affiliation_groups3.json.

    File structure:
        { "canonical": [ {"variant1": count}, {"variant2": count}, ... ], ... }
    """
    with open(groups_path, encoding="utf-8") as f:
        groups = json.load(f)
    mapping = {}
    for canonical, variant_list in groups.items():
        for vdict in variant_list:
            for variant in vdict.keys():
                variant = variant.strip()
                canonical = canonical.strip()
                mapping[variant] = canonical
    return mapping


def org_nodes(g: Graph) -> dict[URIRef, str]:
    """Return {uri: label} for every org node (rdfs:subClassOf schema:Organization)."""
    result = {}
    for subj in g.subjects(RDFS.subClassOf, SCHEMA.Organization):
        lbl = g.value(subj, RDFS.label)
        result[subj] = str(lbl).strip() if lbl else ""
    return result


def _first_component(label: str) -> str:
    """Return the text before the first comma (the department/institute name part)."""
    return label.split(",")[0].strip()


def _leading_ok(old_label: str, canon_label: str, min_lead_sim: float = 0.72) -> bool:
    """
    Require that the FIRST comma-delimited component of both labels is sufficiently
    similar.  This guards against false-positive merges like
      'Interface Science Department, Fritz-Haber Institute ...'
    →  'Theory Department, Fritz-Haber Institute ...'
    where the department names differ but the rest is identical.
    """
    return similarity(_first_component(old_label), _first_component(canon_label)) >= min_lead_sim


def build_merge_map(
    nodes: dict[URIRef, str],
    canonical_map: dict[str, URIRef],
    variant_map: dict[str, str],
    threshold: float,
) -> dict[URIRef, URIRef]:
    """
    Return {old_uri -> (canonical_uri, canon_label, method, score)} for every org
    node that should be merged.

    Strategy (in order of precedence):
      1. Exact label match with a canonical affiliation string  -> identity, skip.
      2. Exact variant match via affiliation_groups3.json
         – Only accepted when the target canonical is in canonical_map AND the
           variant<->canonical similarity >= threshold AND the first-component
           guard passes (prevents bad groupings in the JSON from causing merges
           between unrelated departments).
      3. Fuzzy match: highest-similarity canonical string that exceeds `threshold`,
         subject to the same first-component guard.
    """
    merge = {}
    for uri, label in nodes.items():
        if not label:
            continue

        # 1. Already canonical – nothing to do
        if label in canonical_map:
            continue

        # 2. Exact variant lookup
        if label in variant_map:
            canon_str = variant_map[label]
            if canon_str in canonical_map:
                sim = similarity(label, canon_str)
                if sim >= threshold and _leading_ok(label, canon_str):
                    canon_uri = canonical_map[canon_str]
                    if canon_uri != uri:
                        merge[uri] = (canon_uri, canon_str, "variant-exact", sim)
                    continue
                # failed guard – fall through to fuzzy

        # 3. Fuzzy fallback against all canonical strings
        best_score, best_str, best_uri = 0.0, None, None
        for canon_str, canon_uri in canonical_map.items():
            s = similarity(label, canon_str)
            if s > best_score and _leading_ok(label, canon_str):
                best_score, best_str, best_uri = s, canon_str, canon_uri
        if best_score >= threshold and best_uri != uri:
            merge[uri] = (best_uri, best_str, "fuzzy", best_score)

    return merge


def apply_merge(g: Graph, merge_map: dict[URIRef, tuple]) -> int:
    """
    Rewrite all triples referencing an old URI to use the canonical URI.
    Ensures the canonical URI has rdfs:label, OWL.Class, and
    rdfs:subClassOf schema:Organization triples.
    Returns the number of merged nodes.
    """
    for old_uri, (canon_uri, canon_label, _method, _score) in merge_map.items():
        # Ensure canonical node exists with proper type triples
        if (canon_uri, RDFS.subClassOf, SCHEMA.Organization) not in g:
            g.add((canon_uri, RDF.type, OWL.Class))
            g.add((canon_uri, RDFS.subClassOf, SCHEMA.Organization))
            g.add((canon_uri, RDFS.label, Literal(canon_label)))

        # Migrate all triples where old_uri is the subject
        for p, o in list(g.predicate_objects(old_uri)):
            g.remove((old_uri, p, o))
            # Don't duplicate triples that already exist on canonical
            if (canon_uri, p, o) not in g:
                g.add((canon_uri, p, o))

        # Migrate all triples where old_uri is the object
        for s, p in list(g.subject_predicates(old_uri)):
            g.remove((s, p, old_uri))
            if (s, p, canon_uri) not in g:
                g.add((s, p, canon_uri))

    return len(merge_map)


def strip_carriage_returns(path: str) -> None:
    """Remove Windows \\r characters that rdflib may introduce on re-serialization."""
    with open(path, "rb") as f:
        content = f.read()
    cleaned = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if cleaned != content:
        with open(path, "wb") as f:
            f.write(cleaned)
        print("  ✓ Stripped \\r characters from serialized TTL")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # Ensure Unicode output works on Windows terminals
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write the merged TTL (default: dry-run only)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Similarity threshold for fuzzy matching (default {DEFAULT_THRESHOLD})")
    args = parser.parse_args()

    # ── Load data ──────────────────────────────────────────────────────────
    print("Loading canonical affiliations from cleaned JSON …")
    canonical_map = load_canonical_affiliations(JSON_PATH)
    print(f"  {len(canonical_map)} unique canonical affiliations found\n")

    print("Loading variant->canonical map from affiliation_groups3.json ...")
    variant_map = load_variant_map(GROUPS_PATH)
    print(f"  {len(variant_map)} variant strings indexed\n")

    print("Parsing TTL …")
    g = Graph()
    g.parse(TTL_PATH, format="turtle")
    print(f"  {len(g)} triples loaded\n")

    nodes = org_nodes(g)
    print(f"  {len(nodes)} organization nodes found\n")

    # ── Build merge map ────────────────────────────────────────────────────
    merge_map = build_merge_map(nodes, canonical_map, variant_map, args.threshold)

    if not merge_map:
        print("✅ No duplicate org URIs found – TTL is already normalized.")
        return

    # ── Report ─────────────────────────────────────────────────────────────
    print(f"{'DRY RUN – ' if not args.apply else ''}Found {len(merge_map)} org URI(s) to merge:\n")
    for old_uri, (canon_uri, canon_label, method, score) in sorted(
        merge_map.items(), key=lambda x: x[1][1]
    ):
        old_label = nodes.get(old_uri, "")
        print(f"  [{method} {score:.2f}]")
        print(f"    OLD  URI:   {old_uri}")
        print(f"    OLD  label: {old_label!r}")
        print(f"    NEW  URI:   {canon_uri}")
        print(f"    NEW  label: {canon_label!r}")
        print()

    if not args.apply:
        print("Run with --apply to save the merged TTL.")
        return

    # ── Apply ──────────────────────────────────────────────────────────────
    n = apply_merge(g, merge_map)
    print(f"Merged {n} duplicate org URI(s).  Serializing …")
    g.serialize(destination=TTL_PATH, format="turtle")
    strip_carriage_returns(TTL_PATH)
    print(f"✅ Saved normalized TTL → {TTL_PATH}")


if __name__ == "__main__":
    main()
