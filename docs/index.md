# Katalytikertagung – Abstract Metadata

This site documents the metadata extraction pipeline and search widget for the
**DECHEMA Katalytikertagung** (German Catalysis Conference) abstract collection.

The dataset currently contains **217 approved abstracts** from the 2025 conference.

---

## Search Abstracts

Search by title, author, or affiliation. Click **Read abstract →** to open the
original PDF inline.

<iframe
  src="widgets/search_option_3.html"
  width="100%"
  height="520"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px;">
</iframe>

!!! tip "More options"
    See [Search Options](search-options.md) for compact and accordion variants,
    along with copy-paste `<iframe>` embed codes for all three.

---

## About this project

The abstracts are processed through a three-step pipeline:

1. **Extract** — batch PDF extraction via a local LLM (Ollama) →  `staging.json`
2. **Review** — tkinter GUI for metadata validation and affiliation normalisation → `abstract_metadata.json`
3. **Publish** — this documentation site, auto-generated from the approved dataset

The pipeline is maintained by [NFDI4Cat](https://nfdi4cat.org).
See the [How To](how-to/index.md) section for usage instructions.
