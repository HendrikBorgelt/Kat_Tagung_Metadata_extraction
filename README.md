# Katalytikertagung – Abstract Metadata Extraction & Search Widget

Tools for extracting, reviewing, and publishing metadata from conference abstract PDFs
for the **DECHEMA Katalytikertagung** (German Catalysis Conference).

---

## Overview

The workflow has three stages:

```
PDFs  →  [1_extract.py]  →  staging.json  →  [2_review_gui.py]  →  abstract_metadata.json
                                                                           ↓
                                                               [search_widget/]  →  iframe embed
```

1. **Extract** – batch-process PDF abstracts with a local LLM (Ollama) to pull out title,
   authors, affiliations, keywords and references; results land in a staging buffer.
2. **Review** – a tkinter GUI lets you check each extracted entry against the original PDF,
   resolve affiliation variants, and approve entries into the main dataset.
3. **Publish** – a static search widget (HTML + Fuse.js) is generated from the approved
   dataset and hosted on GitHub Pages / Netlify; DECHEMA embeds it via `<iframe>`.

---

## Repository Structure

```
data/
  abstracts/                    ← source PDFs (not tracked in git)
  abstract_metadata.json        ← approved entries (single source of truth)
  staging.json                  ← entries awaiting review
  affiliation_registry.json     ← {canonical: [variant, ...]} affiliation lookup
  rdf/
    abstracts_katalytikertagung_w_affili_w_classes.ttl  ← RDF/Turtle export
  intermediate/                 ← legacy intermediate files (kept for reference)

scripts/
  pipeline/
    shared.py                   ← shared paths, JSON I/O, affiliation matching
    1_extract.py                ← headless batch extraction CLI
    2_review_gui.py             ← tkinter review + management GUI

  affiliations/                 ← legacy affiliation grouping scripts
  extraction/                   ← legacy extraction GUI scripts
  rdf_conversion/               ← legacy Excel/JSON → RDF conversion scripts
  kg_gui/                       ← legacy knowledge-graph GUI
  delete_abstracts.py           ← legacy deletion tool (TTL + JSON)
  normalize_ttl_affiliations.py ← one-time TTL URI normalization

ontology/
  ontology.ttl                  ← OWL ontology for the abstract dataset
  widoco_config_file            ← Widoco documentation generator config
  widoco_mergerand_modifier_00.py
  widoco_postmodifier_01.py

search_widget/                  ← static HTML search widget (in development)

assets/                         ← logos, presentation slides, mockups
```

---

## Pipeline Scripts

### Prerequisites

```bash
pip install pymupdf pillow
```

Ollama must be running locally with your chosen model pulled:

```bash
ollama pull llama3.2
```

### Step 1 — Extract

Processes all PDFs in `data/abstracts/` and appends results to `data/staging.json`.

```bash
py scripts/pipeline/1_extract.py \
    --input   data/abstracts/   \
    --model   llama3.2          \
    --issued  2025-10-13        \
    --skip-existing
```

| Option | Default | Description |
|---|---|---|
| `--input PATH` | `data/abstracts/` | Folder of PDFs to process |
| `--model NAME` | `llama3.2` | Ollama model name |
| `--issued DATE` | today | `dct:issued` date for this batch (`YYYY-MM-DD`) |
| `--skip-existing` | off | Skip PDFs already in staging or approved |
| `--dry-run` | off | List PDFs that would be processed without calling Ollama |

Entries are saved with `_status: "pending"` (or `"failed"` if extraction failed).

### Step 2 — Review GUI

```bash
py scripts/pipeline/2_review_gui.py
```

**Staged mode** (default) — review pending entries:
- See the original PDF (image + selectable text) alongside extracted metadata
- Edit all fields; resolve each affiliation (map to existing canonical or register as new)
- **Approve** → entry moves to `abstract_metadata.json`; registry updated with any new variants
- **Discard** → removes entry from staging permanently
- **Skip** → leaves entry in staging and advances to the next

**Approved mode** — manage already-approved entries:
- Search by title, author, or affiliation
- Edit any field and save
- Delete individual entries

Granular deletion is available at every level: whole abstract, individual author,
individual affiliation, or individual relation string.

### One-time migration (first run only)

If you have legacy data in `data/intermediate/`, run:

```bash
py scripts/pipeline/shared.py --migrate
```

This copies `metadata_output_*_cleaned_affiliations3.json` → `abstract_metadata.json` and
converts `affiliation_groups3.json` → `affiliation_registry.json`.

---

## Data Files

### `abstract_metadata.json`

Array of approved abstract entries:

```jsonc
{
  "file_title":         "51699_abstract",     // PDF filename without extension
  "dct:title":          "...",
  "dcat:contactPoint":  "A. Smith",           // presenting/corresponding author
  "dcat:keyword":       "catalyst; selectivity",
  "dct:publisher":      "DECHEMA",
  "dcat:theme":         "http://eurovoc.europa.eu/100142",
  "dct:type":           "http://purl.org/spar/fabio/Abstract",
  "dct:issued":         "2025-10-13",
  "dct:language":       "en",
  "authors": [
    { "name": "A. Smith", "affiliations": ["Technische Universität Berlin, Berlin/Germany"] }
  ],
  "dct:relation": ["https://doi.org/10.1234/xyz"]
}
```

### `affiliation_registry.json`

Maps canonical affiliation strings to known variant spellings:

```json
{
  "Technische Universität Berlin, Berlin/Germany": [
    "TU Berlin, Berlin/Germany",
    "Technical University Berlin, Berlin, Germany"
  ]
}
```

### `staging.json`

Same structure as `abstract_metadata.json` plus staging-only fields:

| Field | Purpose |
|---|---|
| `_status` | `"pending"` or `"failed"` |
| `_aff_decisions` | Per-affiliation decision records for the GUI |
| `_raw_affiliations` | Backup of original extracted strings (for Revert) |
| `_error` | Error message if Ollama extraction failed |

---

## RDF / Ontology

The `data/rdf/` folder contains a Turtle export generated from an earlier version of the
dataset. It is kept as-is for Widoco documentation and WebVOWL graphs. New entries are
**not** automatically added to the TTL — the JSON dataset is the active source of truth.

To re-generate the TTL from the JSON, use `scripts/rdf_conversion/json_to_rdf_with_classes_0_0_0.py`
(see that script's docstring for usage).

---

## Search Widget (in development)

A self-contained HTML page with fuzzy search powered by [Fuse.js](https://fusejs.io/),
intended to be embedded via `<iframe>` on the DECHEMA conference website.

- Data baked in as JSON (no backend required)
- Searchable fields: title, authors, affiliations, keywords
- Hosted on GitHub Pages or Netlify
- Zero custom JS on DECHEMA's domain (IT-friendly)

See `search_widget/` for the implementation (in progress).

---

## Legacy Scripts

The scripts in `scripts/affiliations/`, `scripts/extraction/`, `scripts/rdf_conversion/`,
and `scripts/kg_gui/` are from an earlier, multi-step workflow. They remain in the repo
for reference but are no longer the primary workflow. Use the pipeline scripts instead.

---

## Requirements

| Package | Purpose |
|---|---|
| `pymupdf` | PDF text extraction and page rendering |
| `pillow` | PDF page image display in the review GUI |
| `rdflib` | RDF/Turtle parsing and serialisation |
| `tkinter` | Review GUI (included with Python on Windows) |

```bash
pip install pymupdf pillow rdflib
```

Ollama: https://ollama.com/download
