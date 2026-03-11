# Script Reference

## Pipeline scripts

### `scripts/pipeline/1_extract.py` — Batch PDF extraction

Processes PDFs with a local Ollama model and writes results to `data/staging.json`.

```bash
py scripts/pipeline/1_extract.py [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--input PATH` | `data/abstracts/` | Folder of PDFs to process |
| `--model NAME` | `llama3.2` | Ollama model name |
| `--issued DATE` | today | `dct:issued` date for this batch (`YYYY-MM-DD`) |
| `--skip-existing` | off | Skip PDFs already present in staging or approved |
| `--dry-run` | off | List matching PDFs without calling Ollama |

**Output per PDF:**

- `[N/M] file_title  OK` — successfully extracted
- `[N/M] file_title  SKIP` — already exists (with `--skip-existing`)
- `[N/M] file_title  FAIL` — Ollama returned invalid JSON after 2 attempts

---

### `scripts/pipeline/2_review_gui.py` — Review & management GUI

```bash
py scripts/pipeline/2_review_gui.py
```

**Staged mode** — review `staging.json` entries:

| Action | Effect |
|---|---|
| **Approve** | Moves entry to `abstract_metadata.json`; updates `affiliation_registry.json` |
| **Discard** | Permanently removes entry from `staging.json` |
| **Skip** | Advances to next entry without changes |

**Approved mode** — manage `abstract_metadata.json` entries:

| Action | Effect |
|---|---|
| **Save** | Writes edited fields back to `abstract_metadata.json` |
| **Delete** | Removes entry from `abstract_metadata.json` |

**Search filters:** Title / Author / Affiliation (radio buttons in the left pane).

**Granular deletion** (within an entry):

- Remove individual author rows with the **Remove author** button.
- Remove individual affiliation strings with the **x** button per row.

---

### `scripts/pipeline/shared.py` — Shared utilities (migration CLI)

Not normally run directly.  One-time migration from the legacy intermediate files:

```bash
py scripts/pipeline/shared.py --migrate
```

Converts:

- `data/intermediate/metadata_output_*_cleaned_affiliations3.json` → `data/abstract_metadata.json`
- `data/intermediate/affiliation_groups3.json` → `data/affiliation_registry.json`

---

## Search widget

### `search_widget/build.py` — Generate widget HTML files

```bash
py search_widget/build.py
```

Reads `data/abstract_metadata.json` and writes:

| File | Description |
|---|---|
| `docs/widgets/search_option_1.html` | Compact variant |
| `docs/widgets/search_option_2.html` | Accordion variant |
| `docs/widgets/search_option_3.html` | Full details + PDF reader link |
| `docs/widgets/reader.html` | Abstract reader page (metadata + PDF embed) |
| `search_widget/index.html` | Backward-compat copy of option 1 |

Run this script every time `abstract_metadata.json` is updated, then commit
the generated files.

---

## Documentation site

### Install MkDocs

```bash
pip install mkdocs-material
```

### Local preview

```bash
mkdocs serve
```

Opens a live-reload preview at `http://127.0.0.1:8000`.

### Deploy to GitHub Pages

```bash
mkdocs gh-deploy
```

Builds the site and pushes it to the `gh-pages` branch.
The MkDocs hook (`scripts/mkdocs_hooks.py`) automatically copies PDFs from
`data/abstracts/` into the build so they are served at `/abstracts/*.pdf`.

---

## Other scripts

| Script | Purpose |
|---|---|
| `scripts/normalize_ttl_affiliations.py` | One-time TTL URI normalisation (already applied) |
| `scripts/delete_abstracts.py` | Legacy deletion tool for the RDF/TTL file |
| `ontology/widoco_mergerand_modifier_00.py` | Widoco documentation pre-processor |
| `ontology/widoco_postmodifier_01.py` | Widoco documentation post-processor |
