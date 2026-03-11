# How to Add New Abstracts

## Overview

```
New PDFs  →  1_extract.py  →  staging.json  →  2_review_gui.py  →  abstract_metadata.json
                                                                           ↓
                                                               build.py  →  index.html (live)
```

## Step 1 — Place PDFs in the abstracts folder

Copy the new PDF files into `data/abstracts/`.  Filenames should be the
anonymised identifiers (e.g. `52001_abstract.pdf`) — they are never displayed
to end users.

## Step 2 — Run the extraction script

```bash
py scripts/pipeline/1_extract.py \
    --input   data/abstracts/ \
    --model   llama3.2 \
    --issued  2026-10-12 \
    --skip-existing
```

- `--issued` sets the `dct:issued` date for this batch (conference date).
- `--skip-existing` skips PDFs that are already in `staging.json` or
  `abstract_metadata.json`.
- Results are appended to `data/staging.json` with `_status: "pending"`.

!!! note "Ollama must be running"
    Start Ollama before running the script: `ollama serve`
    The default model is `llama3.2`; change with `--model NAME`.

## Step 3 — Review and approve in the GUI

```bash
py scripts/pipeline/2_review_gui.py
```

For each staged entry:

1. Compare the extracted metadata against the original PDF (image + text panel).
2. Edit any incorrect fields directly.
3. Resolve each affiliation decision:
    - **Existing** — map to a known canonical institution name.
    - **New** — register a new canonical name (the registry is updated on approval).
4. Click **Approve** to move the entry to `abstract_metadata.json`.

!!! tip "Failed extractions"
    Entries where Ollama failed to extract valid JSON appear with a `[!]` icon.
    Open them in the GUI, fill in the fields manually, and approve.

## Step 4 — Rebuild the search widget

```bash
py search_widget/build.py
```

This regenerates all three widget variants and the reader page with the updated dataset.

## Step 5 — Commit and push

```bash
git add data/abstract_metadata.json data/affiliation_registry.json \
        docs/widgets/ search_widget/index.html
git commit -m "Add abstracts from [conference] [year]"
git push
```

GitHub Pages updates within a few seconds of the push.
