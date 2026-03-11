"""
mkdocs_hooks.py  —  MkDocs event hooks for the Katalytikertagung documentation site.

Registered in mkdocs.yml under `hooks:`.

on_pre_build:
  Copies PDFs from data/abstracts/ into docs/abstracts/ so that MkDocs includes
  them in the build output and GitHub Pages can serve them for inline viewing.
  The docs/abstracts/ folder is gitignored — this copy is build-time only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC  = _ROOT / "data" / "abstracts"
_DST  = _ROOT / "docs" / "abstracts"


def on_pre_build(config) -> None:
    """Copy PDFs to docs/abstracts/ before MkDocs builds the site."""
    if not _SRC.exists():
        print(f"[hook] data/abstracts/ not found — skipping PDF copy")
        return

    _DST.mkdir(parents=True, exist_ok=True)
    pdfs = list(_SRC.glob("*.pdf"))

    copied = 0
    for pdf in pdfs:
        dst_file = _DST / pdf.name
        # Only copy if missing or source is newer
        if not dst_file.exists() or pdf.stat().st_mtime > dst_file.stat().st_mtime:
            shutil.copy2(pdf, dst_file)
            copied += 1

    print(f"[hook] PDFs: {copied} copied / {len(pdfs)} total → docs/abstracts/")
