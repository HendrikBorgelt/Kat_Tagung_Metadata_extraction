"""
build.py  —  Generate all search widget variants from data/abstract_metadata.json.

Outputs (all self-contained HTML, no backend required):
  docs/widgets/search_option_1.html  — compact, one-line author row
  docs/widgets/search_option_2.html  — accordion: click row to expand details
  docs/widgets/search_option_3.html  — full details + "Read abstract" PDF link
  docs/widgets/search_option_4.html  — compact accordion (50 % wide, 300 px),
                                       "Read abstract" always visible, authors
                                       with indented affiliations + keywords +
                                       references on expand
  docs/widgets/search_option_5.html  — "Search and Display" all-in-one widget:
                                       search + collapsible results + inline PDF
                                       reader in a single iframe; auto-resizes
                                       from 340 px (search only) to 800 px
                                       (search + PDF) via postMessage
  docs/widgets/reader.html           — abstract reader page (metadata + PDF embed)
  search_widget/index.html           — backward-compat copy of option 1

Usage:
    py search_widget/build.py
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

DATA_PATH   = _ROOT / "data" / "abstract_metadata.json"
LOGO_PATH   = _ROOT / "assets" / "Logo_Ohne-BG.png"
WIDGETS_DIR = _ROOT / "docs" / "widgets"
LEGACY_OUT  = _HERE / "index.html"


# ── Data flattening ───────────────────────────────────────────────────────────

def _short_inst(aff: str) -> str:
    return aff.split(",")[0].strip() if aff else ""


def flatten(entry: dict) -> dict:
    authors = entry.get("authors", [])
    contact = entry.get("dcat:contactPoint", "")

    all_affs: list[str] = list(dict.fromkeys(
        aff for a in authors for aff in a.get("affiliations", []) if aff
    ))
    author_names: list[str] = [a["name"] for a in authors if a.get("name")]

    # Contact author first, then remaining authors
    def fmt(a: dict) -> str:
        name = a.get("name", "")
        affs = [af for af in a.get("affiliations", []) if af]
        return f"{name} ({_short_inst(affs[0])})" if affs else name

    ordered = sorted(authors, key=lambda a: 0 if a.get("name") == contact else 1)
    author_display = " \u00b7 ".join(fmt(a) for a in ordered if a.get("name"))

    # Per-author detail list (for accordion and reader)
    author_details = [
        {"name": a.get("name", ""), "affs": a.get("affiliations", [])}
        for a in authors if a.get("name")
    ]

    issued = entry.get("dct:issued", "")
    return {
        "title":         entry.get("dct:title") or entry.get("file_title", ""),
        "contact":       contact,
        "authors":       author_names,
        "affiliations":  all_affs,
        "authorDisplay": author_display,
        "authorDetails": author_details,
        "year":          issued[:4] if issued else "",
        "fileTitle":     entry.get("file_title", ""),
        "keywords":      entry.get("dcat:keyword", "") or "",
        "relations":     entry.get("dct:relation", []) or [],
    }


# ── Logo ──────────────────────────────────────────────────────────────────────

def _logo_html() -> str:
    if LOGO_PATH.exists():
        b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        return (f'<img src="data:image/png;base64,{b64}" '
                f'alt="NFDI4Cat" title="NFDI4Cat">')
    return '<span style="font-size:11px;font-weight:600;color:#aaa">NFDI4Cat</span>'


# ── Shared CSS ────────────────────────────────────────────────────────────────

_COMMON_CSS = """\
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   Arial, sans-serif;
      font-size: 13px; color: #222; background: #fff;
      display: flex; flex-direction: column; height: 100vh; overflow: hidden;
    }
    .search-bar {
      padding: 10px 12px 7px; border-bottom: 1px solid #d0e8f0; flex-shrink: 0;
      background: #edf7fa;
    }
    .input-wrap { position: relative; display: flex; align-items: center; }
    .input-wrap svg {
      position: absolute; left: 8px; pointer-events: none; color: #aaa;
    }
    #q {
      width: 100%; padding: 7px 28px 7px 28px;
      border: 1px solid #ccc; border-radius: 4px;
      font-size: 13px; outline: none; transition: border-color 0.15s;
    }
    #q:focus { border-color: #0057a8; }
    #clear {
      position: absolute; right: 7px; background: none; border: none;
      cursor: pointer; color: #aaa; font-size: 15px;
      display: none; line-height: 1; padding: 2px;
    }
    #clear:hover { color: #444; }
    .filters {
      display: flex; gap: 12px; margin-top: 6px;
    }
    .filters label {
      display: flex; align-items: center; gap: 3px;
      cursor: pointer; color: #555; font-size: 12px; user-select: none;
    }
    .filters input[type=radio] { cursor: pointer; accent-color: #0057a8; }
    #count {
      padding: 4px 12px; font-size: 11px; color: #999;
      border-bottom: 1px solid #ececec; flex-shrink: 0;
    }
    #results { flex: 1; overflow-y: auto; }
    .empty {
      padding: 24px 12px; color: #bbb; text-align: center; font-size: 12px;
    }
    .footer {
      padding: 4px 12px; border-top: 1px solid #ececec;
      display: flex; align-items: center; justify-content: flex-end;
      gap: 5px; flex-shrink: 0;
    }
    .footer-label { font-size: 10px; color: #ccc; }
    .footer a {
      display: flex; align-items: center; gap: 4px; text-decoration: none;
    }
    .footer img { height: 16px; opacity: 0.5; transition: opacity 0.15s; }
    .footer a:hover img { opacity: 0.85; }"""

_SEARCH_BAR = """\
<div class="search-bar">
  <div class="input-wrap">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2.5"
         stroke-linecap="round" stroke-linejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <input id="q" type="text" placeholder="Search abstracts\u2026"
           autocomplete="off" spellcheck="false">
    <button id="clear" title="Clear">&#x2715;</button>
  </div>
  <div class="filters">
    <label><input type="radio" name="f" value="all" checked> All</label>
    <label><input type="radio" name="f" value="title"> Title</label>
    <label><input type="radio" name="f" value="author"> Author</label>
    <label><input type="radio" name="f" value="affiliation"> Affiliation</label>
  </div>
</div>"""

_FOOTER = """\
<div class="footer">
  <span class="footer-label">Provided by</span>
  <a href="https://nfdi4cat.org" target="_blank" rel="noopener noreferrer">
    __LOGO_HTML__
  </a>
</div>"""

_FUSE_CDN = ('https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js')

_SEARCH_JS = """\
  var KEY_MAP = {
    all:         ["title", "authors", "affiliations"],
    title:       ["title"],
    author:      ["authors"],
    affiliation: ["affiliations"]
  };
  function makeFuse(field) {
    return new Fuse(DATA, {
      keys: KEY_MAP[field], threshold: 0.35,
      ignoreLocation: true, includeScore: false
    });
  }
  var fuse = makeFuse("all");
  var qEl = document.getElementById("q");
  var clearEl = document.getElementById("clear");
  var countEl = document.getElementById("count");
  var resultsEl = document.getElementById("results");
  function esc(s) {
    return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")
                  .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function render(items) {
    var q = qEl.value.trim();
    countEl.textContent = items.length === DATA.length
      ? DATA.length + " abstracts"
      : items.length + " result" + (items.length===1?"":"s");
    if (q && items.length===0) {
      resultsEl.innerHTML = '<div class="empty">No results for \u201c'+esc(q)+'\u201d</div>';
      return;
    }
    resultsEl.innerHTML = items.map(function(d){ return renderRow(d); }).join("");
  }
  function search() {
    var q = qEl.value.trim();
    clearEl.style.display = q ? "block" : "none";
    render(q ? fuse.search(q).map(function(r){return r.item;}) : DATA);
  }
  qEl.addEventListener("input", search);
  clearEl.addEventListener("click", function() {
    qEl.value=""; clearEl.style.display="none"; render(DATA); qEl.focus();
  });
  document.querySelectorAll("input[name=f]").forEach(function(r) {
    r.addEventListener("change", function(){ fuse=makeFuse(r.value); search(); });
  });"""


# ── HTML assembler ────────────────────────────────────────────────────────────

def _assemble(page_title: str, extra_css: str,
              render_row_js: str, extra_js: str = "",
              extra_html: str = "") -> str:
    footer = _FOOTER.replace("__LOGO_HTML__", _logo_html())
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <style>
{_COMMON_CSS}
{extra_css}
  </style>
</head>
<body>
{_SEARCH_BAR}
<div id="count"></div>
<div id="results"></div>
{extra_html}{footer}
<script src="{_FUSE_CDN}"></script>
<script>
(function() {{
  var DATA = __DATA_JSON__;
{_SEARCH_JS}
  function renderRow(d) {{
{render_row_js}
  }}
{extra_js}
  render(DATA);
}}());
</script>
</body>
</html>"""


# ── Option 1: compact ─────────────────────────────────────────────────────────

_OPT1_CSS = """\
    .row {
      padding: 7px 12px; border-bottom: 1px solid #f2f2f2;
    }
    .row:hover { background: #fafafa; }
    .row-title {
      font-weight: 500; color: #111; line-height: 1.35;
    }
    .row-year {
      float: right; font-size: 11px; color: #bbb; margin-left: 8px; margin-top: 1px;
    }
    .row-meta {
      font-size: 11px; color: #888; margin-top: 2px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .row-contact { font-weight: 500; color: #666; }"""

_OPT1_ROW = """\
    var contact = d.contact ? '<span class="row-contact">'+esc(d.contact)+'</span>' : '';
    var sep = contact && d.authorDisplay ? ' \u00b7 ' : '';
    return '<div class="row">'
      + '<div class="row-title">'
      +   '<span class="row-year">'+esc(d.year)+'</span>'
      +   esc(d.title)
      + '</div>'
      + '<div class="row-meta">'+contact+sep+esc(d.authorDisplay)+'</div>'
      + '</div>';"""


# ── Option 2: accordion ───────────────────────────────────────────────────────

_OPT2_CSS = """\
    .row { border-bottom: 1px solid #f2f2f2; }
    .row-hdr {
      padding: 7px 12px; cursor: pointer;
      display: flex; align-items: baseline; gap: 6px;
    }
    .row-hdr:hover { background: #fafafa; }
    .arrow { font-size: 9px; color: #aaa; flex-shrink: 0; margin-top: 2px; }
    .row-title { font-weight: 500; color: #111; flex: 1; line-height: 1.35; }
    .row-year { font-size: 11px; color: #bbb; flex-shrink: 0; }
    .row-contact-hdr { font-size: 11px; color: #888; flex-shrink: 0; }
    .row-body {
      display: none; padding: 0 12px 8px 24px;
      font-size: 12px; color: #555; line-height: 1.7;
    }
    .row-body.open { display: block; }
    .detail-author { display: block; }
    .detail-affs { color: #999; margin-left: 8px; }"""

_OPT2_ROW = """\
    var contact = d.contact ? ' \u00b7 ' + esc(d.contact) : '';
    var details = (d.authorDetails||[]).map(function(a) {
      var affs = a.affs && a.affs.length
        ? '<span class="detail-affs">'+esc(a.affs.join("; "))+'</span>' : '';
      return '<span class="detail-author">'+esc(a.name)+affs+'</span>';
    }).join("");
    return '<div class="row">'
      + '<div class="row-hdr">'
      +   '<span class="arrow">&#9654;</span>'
      +   '<span class="row-title">'+esc(d.title)+'</span>'
      +   '<span class="row-contact-hdr">'+contact+'</span>'
      +   '<span class="row-year">'+esc(d.year)+'</span>'
      + '</div>'
      + '<div class="row-body">'+details+'</div>'
      + '</div>';"""

_OPT2_EXTRA_JS = """\
  document.addEventListener("click", function(e) {
    var hdr = e.target.closest(".row-hdr");
    if (!hdr) return;
    var body = hdr.nextElementSibling;
    var isOpen = body.classList.contains("open");
    body.classList.toggle("open", !isOpen);
    hdr.querySelector(".arrow").innerHTML = isOpen ? "&#9654;" : "&#9660;";
  });"""


# ── Option 3: full details + PDF reader link ──────────────────────────────────

_OPT3_CSS = """\
    .row {
      padding: 8px 12px 10px; border-bottom: 1px solid #f2f2f2;
    }
    .row:hover { background: #fafafa; }
    .row-title {
      font-weight: 500; color: #111; line-height: 1.35;
    }
    .row-year {
      float: right; font-size: 11px; color: #bbb; margin-left: 8px; margin-top: 2px;
    }
    .row-contact {
      font-size: 11px; color: #888; margin-top: 2px;
    }
    .row-contact em { font-style: normal; font-weight: 500; color: #555; }
    .row-authors {
      font-size: 11px; color: #888; margin-top: 2px; line-height: 1.5;
    }
    .row-footer {
      display: flex; justify-content: flex-end; margin-top: 4px;
    }
    .read-link {
      font-size: 11px; color: #0057a8; text-decoration: none;
      border: 1px solid #c8daef; border-radius: 3px;
      padding: 2px 7px;
    }
    .read-link:hover { background: #eef4fb; }"""

_OPT3_ROW = """\
    var readLink = d.fileTitle
      ? '<a class="read-link" href="./reader.html?id='+esc(d.fileTitle)
          +'" target="_blank">Read abstract \u2192</a>'
      : '';
    var contact = d.contact
      ? '<div class="row-contact">Presenting: <em>'+esc(d.contact)+'</em></div>'
      : '';
    return '<div class="row">'
      + '<div class="row-title">'
      +   '<span class="row-year">'+esc(d.year)+'</span>'
      +   esc(d.title)
      + '</div>'
      + contact
      + '<div class="row-authors">'+esc(d.authorDisplay)+'</div>'
      + '<div class="row-footer">'+readLink+'</div>'
      + '</div>';"""


# ── Option 4: compact accordion (50 % wide, 300 px) ──────────────────────────
# Always-visible area: presenting author + "Read abstract" button.
# Expand area: full author list with affiliations indented one level, then
# keywords and references in a separated block when available.

_OPT4_CSS = """\
    .row { border-bottom: 1px solid #f2f2f2; }
    .row-hdr {
      padding: 6px 10px 3px; cursor: pointer;
      display: flex; align-items: baseline; gap: 5px;
    }
    .row-hdr:hover { background: #fafafa; }
    .arrow { font-size: 9px; color: #aaa; flex-shrink: 0; margin-top: 2px; }
    .row-title { font-weight: 500; color: #111; flex: 1; line-height: 1.3; }
    .row-year  { font-size: 11px; color: #bbb; flex-shrink: 0; }
    .row-always {
      padding: 0 10px 5px 24px;
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
    }
    .row-contact { font-size: 11px; color: #555; font-weight: 500; flex: 1;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .read-link {
      font-size: 11px; color: #0057a8; text-decoration: none; white-space: nowrap;
      border: 1px solid #c8daef; border-radius: 3px; padding: 1px 6px; flex-shrink: 0;
    }
    .read-link:hover { background: #eef4fb; }
    .row-body {
      display: none; padding: 4px 10px 8px 24px;
      font-size: 11px; color: #555; line-height: 1.5;
    }
    .row-body.open { display: block; }
    .detail-author { margin-bottom: 3px; }
    .detail-name   { color: #333; }
    .detail-aff    { padding-left: 14px; color: #999; line-height: 1.4; }
    .detail-section {
      margin-top: 5px; padding-top: 5px; border-top: 1px solid #f0f0f0;
    }
    .detail-lbl  { font-weight: 500; color: #666; }
    .detail-kw   { color: #888; margin-top: 3px; }
    .detail-rels { color: #888; margin-top: 2px; }"""

_OPT4_ROW = """\
    var readLink = d.fileTitle
      ? '<a class="read-link" href="./reader.html?id='+esc(d.fileTitle)
          +'" target="_blank">Read abstract \u2192</a>'
      : '';
    var contact = d.contact
      ? '<span class="row-contact">'+esc(d.contact)+'</span>'
      : '';
    var details = (d.authorDetails||[]).map(function(a) {
      var affsHtml = (a.affs||[]).map(function(af) {
        return '<div class="detail-aff">'+esc(af)+'</div>';
      }).join("");
      return '<div class="detail-author">'
        + '<div class="detail-name">'+esc(a.name)+'</div>'
        + affsHtml
        + '</div>';
    }).join("");
    var kw = d.keywords
      ? '<div class="detail-kw"><span class="detail-lbl">Keywords: </span>'
          +esc(d.keywords)+'</div>'
      : '';
    var rels = (d.relations||[]).length
      ? '<div class="detail-rels"><span class="detail-lbl">References: </span>'
          +(d.relations||[]).map(function(r){return esc(r);}).join("; ")+'</div>'
      : '';
    var extra = (kw||rels) ? '<div class="detail-section">'+kw+rels+'</div>' : '';
    var alwaysContent = contact+readLink;
    return '<div class="row">'
      + '<div class="row-hdr">'
      +   '<span class="arrow">&#9654;</span>'
      +   '<span class="row-title">'+esc(d.title)+'</span>'
      +   '<span class="row-year">'+esc(d.year)+'</span>'
      + '</div>'
      + (alwaysContent ? '<div class="row-always">'+alwaysContent+'</div>' : '')
      + '<div class="row-body">'+details+extra+'</div>'
      + '</div>';"""

_OPT4_EXTRA_JS = """\
  document.addEventListener("click", function(e) {
    // "Read abstract" link: when embedded in a parent page, post the reader
    // URL to the parent instead of opening a new tab, so the parent can
    // display the PDF in a sibling iframe.  Falls back to normal new-tab
    // behaviour when the widget is used standalone.
    var link = e.target.closest(".read-link");
    if (link) {
      if (window.parent !== window) {
        e.preventDefault();
        window.parent.postMessage(
          { type: "katTagung_openReader", url: link.href }, "*"
        );
      }
      return;
    }
    // Accordion toggle (click on .row-hdr only, not on .row-always)
    var hdr = e.target.closest(".row-hdr");
    if (!hdr) return;
    var body   = hdr.closest(".row").querySelector(".row-body");
    var isOpen = body.classList.contains("open");
    body.classList.toggle("open", !isOpen);
    hdr.querySelector(".arrow").innerHTML = isOpen ? "&#9654;" : "&#9660;";
  });"""


# ── Option 5: Search and Display Box ─────────────────────────────────────────
# A single self-contained widget.  Results are always shown (collapsed accordion
# rows).  Clicking "Read abstract" expands an inline reader pane below the
# results list and notifies the parent page to resize the iframe from ~340 px to
# ~800 px via postMessage({ type:"katTagung_resize", height:<n> }).

_OPT5_CSS = """\
    /* Results: capped height; compressed further when reader is open */
    #results { flex: none; max-height: 230px; overflow-y: auto; }
    body.reader-open #results { max-height: 150px; }
    .row { border-bottom: 1px solid #f2f2f2; }
    .row-hdr {
      padding: 6px 10px 3px; cursor: pointer;
      display: flex; align-items: baseline; gap: 5px;
    }
    .row-hdr:hover { background: #fafafa; }
    .arrow { font-size: 9px; color: #aaa; flex-shrink: 0; margin-top: 2px; }
    .row-title { font-weight: 500; color: #111; flex: 1; line-height: 1.3; }
    .row-year  { font-size: 11px; color: #bbb; flex-shrink: 0; }
    .row-always {
      padding: 0 10px 5px 24px;
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
    }
    .row-contact { font-size: 11px; color: #555; font-weight: 500; flex: 1;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .read-link {
      font-size: 11px; color: #0057a8; text-decoration: none; white-space: nowrap;
      border: 1px solid #c8daef; border-radius: 3px; padding: 1px 6px; flex-shrink: 0;
    }
    .read-link:hover { background: #eef4fb; }
    .row-body {
      display: none; padding: 4px 10px 8px 24px;
      font-size: 11px; color: #555; line-height: 1.5;
    }
    .row-body.open { display: block; }
    .detail-author  { margin-bottom: 3px; }
    .detail-name    { color: #333; }
    .detail-aff     { padding-left: 14px; color: #999; line-height: 1.4; }
    .detail-section { margin-top: 5px; padding-top: 5px; border-top: 1px solid #f0f0f0; }
    .detail-lbl     { font-weight: 500; color: #666; }
    .detail-kw      { color: #888; margin-top: 3px; }
    .detail-rels    { color: #888; margin-top: 2px; }
    /* Reader pane — hidden until a result is opened */
    .reader-pane {
      display: none; flex-direction: column; flex: 1; min-height: 0;
      border-top: 2px solid #e0e0e0;
    }
    body.reader-open .reader-pane { display: flex; }
    .rdr-hdr {
      padding: 5px 12px; display: flex; align-items: center; gap: 8px;
      border-bottom: 1px solid #ececec; flex-shrink: 0;
    }
    .rdr-back {
      background: none; border: 1px solid #ccc; border-radius: 3px;
      padding: 2px 8px; font-size: 11px; cursor: pointer; color: #555; flex-shrink: 0;
    }
    .rdr-back:hover { background: #f5f5f5; }
    .rdr-title {
      font-size: 12px; font-weight: 500; color: #333; flex: 1;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .rdr-meta {
      padding: 5px 12px; font-size: 11px; color: #666; line-height: 1.5;
      border-bottom: 1px solid #ececec; flex-shrink: 0;
      max-height: 90px; overflow-y: auto;
    }
    .rdr-meta-author { display: block; }
    .rdr-meta-aff    { display: block; padding-left: 14px; color: #999; }
    /* pdf-wrap is a flex column so both the loading div and the iframe
       can use flex:1 to reliably fill the remaining height */
    .rdr-pdf-wrap {
      flex: 1; min-height: 0; padding: 6px 12px 8px;
      display: flex; flex-direction: column;
    }
    .rdr-pdf-wrap iframe {
      flex: 1; width: 100%; border: 1px solid #ddd; border-radius: 3px;
      min-height: 0;
    }
    .rdr-loading {
      flex: 1; display: flex; align-items: center; justify-content: center;
      color: #bbb; font-size: 12px; letter-spacing: 0.02em;
      border: 1px dashed #e0e0e0; border-radius: 3px;
    }"""

# Extra HTML injected between #results and the footer — the inline reader pane.
_OPT5_HTML = """\
<div id="reader-pane" class="reader-pane">
  <div class="rdr-hdr">
    <button id="rdr-back" class="rdr-back">&#8592; Back</button>
    <span id="rdr-title" class="rdr-title"></span>
  </div>
  <div id="rdr-meta" class="rdr-meta"></div>
  <div class="rdr-pdf-wrap">
    <!-- Loading placeholder: visible while parent iframe is resizing and
         the PDF has not yet started rendering. -->
    <div id="rdr-loading" class="rdr-loading">Loading PDF&#8230;</div>
    <!-- PDF iframe: hidden until the 250 ms resize-settle delay has passed,
         so the browser PDF viewer always initialises at the correct height. -->
    <iframe id="rdr-pdf" src="about:blank" title="Abstract PDF"
            style="display:none; flex:1;"></iframe>
  </div>
</div>
"""

# Row template: same accordion shape as Option 4 but "Read abstract" uses
# data-id (no href navigation — the reader opens inside the same widget).
_OPT5_ROW = """\
    var readLink = d.fileTitle
      ? '<a class="read-link" href="#" data-id="'+esc(d.fileTitle)+'">Read abstract \u2192</a>'
      : '';
    var contact = d.contact
      ? '<span class="row-contact">'+esc(d.contact)+'</span>'
      : '';
    var details = (d.authorDetails||[]).map(function(a) {
      var affsHtml = (a.affs||[]).map(function(af) {
        return '<div class="detail-aff">'+esc(af)+'</div>';
      }).join("");
      return '<div class="detail-author">'
        + '<div class="detail-name">'+esc(a.name)+'</div>'
        + affsHtml
        + '</div>';
    }).join("");
    var kw = d.keywords
      ? '<div class="detail-kw"><span class="detail-lbl">Keywords: </span>'
          +esc(d.keywords)+'</div>'
      : '';
    var rels = (d.relations||[]).length
      ? '<div class="detail-rels"><span class="detail-lbl">References: </span>'
          +(d.relations||[]).map(function(r){return esc(r);}).join("; ")+'</div>'
      : '';
    var extra = (kw||rels) ? '<div class="detail-section">'+kw+rels+'</div>' : '';
    var alwaysContent = contact+readLink;
    return '<div class="row">'
      + '<div class="row-hdr">'
      +   '<span class="arrow">&#9654;</span>'
      +   '<span class="row-title">'+esc(d.title)+'</span>'
      +   '<span class="row-year">'+esc(d.year)+'</span>'
      + '</div>'
      + (alwaysContent ? '<div class="row-always">'+alwaysContent+'</div>' : '')
      + '<div class="row-body">'+details+extra+'</div>'
      + '</div>';"""

_OPT5_EXTRA_JS = """\
  var HEIGHT_CLOSED = 340;
  var HEIGHT_OPEN   = 800;

  function notifyResize(h) {
    if (window.parent !== window) {
      window.parent.postMessage({ type: "katTagung_resize", height: h }, "*");
    }
  }

  function openReader(fileTitle) {
    var entry = null;
    for (var i = 0; i < DATA.length; i++) {
      if (DATA[i].fileTitle === fileTitle) { entry = DATA[i]; break; }
    }
    if (!entry) return;
    // Populate header title
    document.getElementById("rdr-title").textContent = entry.title || "";
    // Populate meta: authors + affiliations; mark presenting author
    var authHtml = (entry.authorDetails || []).map(function(a) {
      var affs = (a.affs || []).map(function(af) {
        return '<span class="rdr-meta-aff">'+esc(af)+'</span>';
      }).join("");
      return '<span class="rdr-meta-author">'
        + esc(a.name)
        + (entry.contact === a.name
            ? ' <em style="color:#0057a8;font-style:normal;">\u2605</em>' : "")
        + '</span>' + affs;
    }).join("");
    document.getElementById("rdr-meta").innerHTML = authHtml;
    // Reset PDF state: show loading placeholder, hide iframe
    var pdfEl      = document.getElementById("rdr-pdf");
    var loadingEl  = document.getElementById("rdr-loading");
    pdfEl.style.display     = "none";
    pdfEl.src               = "about:blank";
    loadingEl.style.display = "flex";
    loadingEl.textContent   = "Loading PDF\u2026";
    // Reveal reader pane and ask parent page to expand the iframe
    document.getElementById("reader-pane").classList.add("open");
    document.body.classList.add("reader-open");
    notifyResize(HEIGHT_OPEN);
    // Delay loading the PDF until AFTER the parent-iframe resize transition
    // has fully completed.  The embed code uses "transition: height 0.4s ease",
    // so waiting 450 ms (just past 400 ms) guarantees the PDF viewer always
    // initialises at the final 800 px height, not at a mid-animation height.
    var pdfSrc = "../abstracts/" + encodeURIComponent(fileTitle) + ".pdf";
    setTimeout(function() {
      pdfEl.onload = function() {
        loadingEl.style.display = "none";
        pdfEl.style.display     = "flex";
      };
      // Fallback: browser PDF viewers often do not fire the iframe onload
      // event reliably.  Keep "Loading PDF…" visible for up to 30 s so the
      // user sees feedback while the file downloads, then reveal the iframe
      // unconditionally (PDF should be rendered by then in most cases).
      setTimeout(function() {
        loadingEl.style.display = "none";
        pdfEl.style.display     = "flex";
      }, 30000);
      pdfEl.src = pdfSrc;
    }, 450);
  }

  function closeReader() {
    var pdfEl     = document.getElementById("rdr-pdf");
    var loadingEl = document.getElementById("rdr-loading");
    document.getElementById("reader-pane").classList.remove("open");
    document.body.classList.remove("reader-open");
    pdfEl.src               = "about:blank";
    pdfEl.style.display     = "none";
    loadingEl.style.display = "flex";
    loadingEl.textContent   = "Loading PDF\u2026";
    notifyResize(HEIGHT_CLOSED);
  }

  document.getElementById("rdr-back").addEventListener("click", closeReader);

  document.addEventListener("click", function(e) {
    // "Read abstract" opens the inline reader pane
    var link = e.target.closest(".read-link");
    if (link) {
      e.preventDefault();
      openReader(link.getAttribute("data-id"));
      return;
    }
    // Accordion toggle (header only, not .row-always)
    var hdr = e.target.closest(".row-hdr");
    if (!hdr) return;
    var body   = hdr.closest(".row").querySelector(".row-body");
    var isOpen = body.classList.contains("open");
    body.classList.toggle("open", !isOpen);
    hdr.querySelector(".arrow").innerHTML = isOpen ? "&#9654;" : "&#9660;";
  });"""


# ── Reader page ───────────────────────────────────────────────────────────────

def _reader_html() -> str:
    footer = _FOOTER.replace("__LOGO_HTML__", _logo_html())
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Abstract Reader</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   Arial, sans-serif;
      font-size: 13px; color: #222; background: #fff;
      display: flex; flex-direction: column; height: 100vh;
    }
    .header {
      padding: 10px 14px 8px; border-bottom: 1px solid #e0e0e0; flex-shrink: 0;
    }
    .back-link {
      font-size: 12px; color: #0057a8; text-decoration: none; cursor: pointer;
    }
    .back-link:hover { text-decoration: underline; }
    .meta { padding: 10px 14px; flex-shrink: 0; }
    .meta-title {
      font-size: 15px; font-weight: 600; line-height: 1.4; color: #111;
      margin-bottom: 8px;
    }
    .meta-row {
      font-size: 12px; color: #666; margin-top: 3px; line-height: 1.5;
    }
    .meta-row strong { color: #444; }
    .meta-author { display: block; margin-left: 8px; }
    .meta-aff { color: #999; margin-left: 4px; }
    .pdf-wrap {
      flex: 1; display: flex; flex-direction: column;
      padding: 0 14px 10px; min-height: 0;
    }
    .pdf-wrap iframe {
      flex: 1; width: 100%; border: 1px solid #ddd; border-radius: 3px;
      min-height: 0;
    }
    .pdf-fallback {
      flex: 1; display: flex; align-items: center; justify-content: center;
      color: #999; font-size: 12px; text-align: center; line-height: 1.8;
    }
    .pdf-fallback a { color: #0057a8; }
    .footer {
      padding: 4px 14px; border-top: 1px solid #ececec;
      display: flex; align-items: center; justify-content: flex-end;
      gap: 5px; flex-shrink: 0;
    }
    .footer-label { font-size: 10px; color: #ccc; }
    .footer a { display: flex; align-items: center; gap: 4px; text-decoration: none; }
    .footer img { height: 16px; opacity: 0.5; transition: opacity 0.15s; }
    .footer a:hover img { opacity: 0.85; }
    #not-found {
      padding: 40px 14px; color: #bbb; text-align: center; font-size: 13px;
    }
  </style>
</head>
<body>
<div class="header">
  <a class="back-link" onclick="history.back()">&#8592; Back</a>
</div>
<div id="meta" class="meta" style="display:none"></div>
<div id="pdf-wrap" class="pdf-wrap" style="display:none"></div>
<div id="not-found" style="display:none">Abstract not found.</div>
__FOOTER__
<script>
(function() {
  var DATA = __DATA_JSON__;

  function esc(s) {
    return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")
                  .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  var params = new URLSearchParams(window.location.search);
  var id     = params.get("id") || "";
  var entry  = DATA.filter(function(d){ return d.fileTitle === id; })[0];

  if (!entry) {
    document.getElementById("not-found").style.display = "block";
    document.title = "Abstract not found";
    return;
  }

  // ── Metadata panel ────────────────────────────────────────
  document.title = entry.title || "Abstract";

  var authorsHtml = (entry.authorDetails||[]).map(function(a) {
    var affs = a.affs && a.affs.length
      ? '<span class="meta-aff">(' + esc(a.affs.join("; ")) + ')</span>' : "";
    return '<span class="meta-author">'
      + esc(a.name) + affs
      + (entry.contact === a.name ? ' <em style="color:#0057a8">(presenting)</em>' : "")
      + '</span>';
  }).join("");

  var metaEl = document.getElementById("meta");
  metaEl.innerHTML =
    '<div class="meta-title">' + esc(entry.title) + '</div>'
    + '<div class="meta-row"><strong>Year:</strong> ' + esc(entry.year) + '</div>'
    + (entry.contact
        ? '<div class="meta-row"><strong>Presenting:</strong> ' + esc(entry.contact) + '</div>'
        : "")
    + '<div class="meta-row"><strong>Authors:</strong>'
    + authorsHtml + '</div>';
  metaEl.style.display = "block";

  // ── PDF embed ─────────────────────────────────────────────
  if (entry.fileTitle) {
    var pdfUrl = "../abstracts/" + esc(entry.fileTitle) + ".pdf";
    var wrap   = document.getElementById("pdf-wrap");
    wrap.innerHTML =
      '<iframe src="' + pdfUrl + '" type="application/pdf">'
      + '<div class="pdf-fallback">'
      + 'Your browser cannot display the PDF inline.<br>'
      + '<a href="' + pdfUrl + '" target="_blank">Open PDF \u2197</a>'
      + '</div>'
      + '</iframe>';
    wrap.style.display = "flex";
  }
}());
</script>
</body>
</html>""".replace("__FOOTER__", footer)


# ── Knowledge Graph widget ────────────────────────────────────────────────────

_KG_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Katalytikertagung \u2013 Knowledge Graph</title>
  <script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.29.2/cytoscape.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      font-size: 13px; color: #222; background: #fff;
      display: flex; flex-direction: column; height: 100vh; overflow: hidden;
    }
    #toolbar {
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      padding: 8px 12px 6px; border-bottom: 1px solid #d0e8f0; flex-shrink: 0;
      background: #edf7fa;
    }
    #mode-btns { display: flex; gap: 4px; flex-shrink: 0; }
    .mode-btn {
      padding: 4px 10px; border: 1px solid #ccc; border-radius: 12px;
      background: #f5f5f5; cursor: pointer; font-size: 12px; transition: all 0.15s;
    }
    .mode-btn.active { background: #0057a8; color: #fff; border-color: #0057a8; }
    .mode-btn:hover:not(.active) { background: #e8e8e8; }
    #search-wrap { position: relative; flex: 1; min-width: 120px; }
    #q {
      width: 100%; padding: 5px 26px 5px 8px;
      border: 1px solid #ccc; border-radius: 4px; font-size: 12px; outline: none;
      transition: border-color 0.15s;
    }
    #q:focus { border-color: #0057a8; }
    #clear {
      position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
      background: none; border: none; cursor: pointer; color: #aaa; font-size: 14px;
      line-height: 1; display: none;
    }
    #clear:hover { color: #444; }
    #suggestions {
      position: absolute; top: 100%; left: 0; right: 0; z-index: 999;
      background: #fff; border: 1px solid #ccc; border-top: none;
      border-radius: 0 0 4px 4px; max-height: 200px; overflow-y: auto;
      box-shadow: 0 4px 8px rgba(0,0,0,0.08);
    }
    .suggestion {
      padding: 6px 10px; cursor: pointer; font-size: 12px;
      border-bottom: 1px solid #f0f0f0; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis;
    }
    .suggestion:hover { background: #f0f4ff; }
    #dist-wrap { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
    #dist-label { font-size: 11px; color: #666; white-space: nowrap; }
    #dist-btns  { display: flex; gap: 3px; }
    .dist-btn {
      width: 28px; height: 24px; border: 1px solid #ccc; border-radius: 4px;
      background: #f5f5f5; cursor: pointer; font-size: 12px; font-weight: 600;
      transition: all 0.15s;
    }
    .dist-btn.active { background: #0057a8; color: #fff; border-color: #0057a8; }
    .dist-btn:hover:not(.active) { background: #e8e8e8; }
    #cy-wrap { position: relative; flex: 1; min-height: 0; }
    #cy { width: 100%; height: 100%; }
    #kg-legend {
      position: absolute; bottom: 10px; left: 10px; z-index: 10;
      background: rgba(255,255,255,0.90); border: 1px solid #ddd;
      border-radius: 6px; padding: 6px 10px; font-size: 11px; color: #333;
      pointer-events: none; line-height: 1.4;
    }
    .lg-row { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
    .lg-dot { display: inline-block; width: 13px; height: 13px; flex-shrink: 0; }
    #detail {
      height: 130px; flex-shrink: 0;
      border-top: 1px solid #e0e0e0; padding: 8px 12px;
      overflow-y: auto; background: #fafafa;
    }
    #detail-hint { color: #bbb; font-size: 12px; text-align: center; padding-top: 40px; }
    #detail-content { display: none; }
    .detail-badge {
      display: inline-block; padding: 1px 8px; border-radius: 10px;
      font-size: 10px; font-weight: 600; color: #fff; margin-bottom: 4px;
      text-transform: capitalize;
    }
    .type-author      { background: #4A90D9; }
    .type-abstract    { background: #E8A838; }
    .type-affiliation { background: #5BAD6F; }
    #detail-title {
      font-weight: 600; font-size: 13px; margin-bottom: 4px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .detail-section { font-size: 12px; color: #444; margin-top: 3px; line-height: 1.5; }
    .detail-section a { color: #0057a8; text-decoration: none; }
    .detail-section a:hover { text-decoration: underline; }
    .footer {
      padding: 4px 12px; border-top: 1px solid #ececec;
      display: flex; align-items: center; justify-content: flex-end;
      gap: 5px; flex-shrink: 0;
    }
    .footer-label { font-size: 10px; color: #ccc; }
    .footer a { display: flex; align-items: center; gap: 4px; text-decoration: none; }
    .footer img { height: 16px; opacity: 0.5; transition: opacity 0.15s; }
    .footer a:hover img { opacity: 0.85; }
  </style>
</head>
<body>

<div id="toolbar">
  <div id="mode-btns">
    <button class="mode-btn active" data-mode="author">Authors</button>
    <button class="mode-btn" data-mode="abstract">Abstracts</button>
    <button class="mode-btn" data-mode="affiliation">Affiliations</button>
  </div>
  <div id="search-wrap">
    <input id="q" type="text" placeholder="Search authors\u2026"
           autocomplete="off" spellcheck="false">
    <button id="clear" title="Clear">\u2715</button>
    <div id="suggestions"></div>
  </div>
  <div id="dist-wrap">
    <span id="dist-label">Level:</span>
    <div id="dist-btns">
      <button class="dist-btn active" data-dist="1">1</button>
      <button class="dist-btn" data-dist="2">2</button>
      <button class="dist-btn" data-dist="3">3</button>
      <button class="dist-btn" data-dist="4">4</button>
    </div>
  </div>
</div>

<div id="cy-wrap">
  <div id="cy"></div>
  <div id="kg-legend">
    <div class="lg-row">
      <span class="lg-dot" style="background:#4A90D9;border-radius:3px"></span> Author
    </div>
    <div class="lg-row">
      <span class="lg-dot" style="background:#E8A838;border-radius:3px"></span> Abstract
    </div>
    <div class="lg-row">
      <span class="lg-dot" style="background:#5BAD6F;border-radius:50%"></span> Affiliation
    </div>
  </div>
</div>

<div id="detail">
  <div id="detail-hint">Click a node to see details \u2014 click an author node to make it the focus</div>
  <div id="detail-content">
    <span id="detail-badge" class="detail-badge"></span>
    <div id="detail-title"></div>
    <div id="detail-body"></div>
  </div>
</div>

<div class="footer">
  <span class="footer-label">Provided by</span>
  <a href="https://nfdi4cat.org" target="_blank" rel="noopener noreferrer">
    __LOGO_HTML__
  </a>
</div>

<script>
(function () {
"use strict";

var DATA = __DATA_JSON__;

// ── 1. Build graph data structures ───────────────────────────────────────────

var authorNodes   = {};
var affNodes      = {};
var abstractNodes = {};

var abstractsByAuthor = {};
var authorsByAbstract = {};
var affsByAuthor      = {};
var authorsByAff      = {};

function _addUniq(map, key, val) {
  if (!map[key]) map[key] = [];
  if (map[key].indexOf(val) === -1) map[key].push(val);
}

DATA.forEach(function (d) {
  var absId = "a:" + d.fileTitle;
  var lbl   = d.title.length > 38 ? d.title.slice(0, 38) + "\u2026" : d.title;
  abstractNodes[d.fileTitle] = {
    id: absId, type: "abstract", label: lbl,
    title: d.title, year: d.year, contact: d.contact,
    keywords: d.keywords, fileTitle: d.fileTitle
  };
  (d.authorDetails || []).forEach(function (au) {
    var auId = "u:" + au.name;
    if (!authorNodes[au.name])
      authorNodes[au.name] = { id: auId, type: "author", label: au.name };
    _addUniq(abstractsByAuthor, auId, absId);
    _addUniq(authorsByAbstract, absId, auId);
    (au.affs || []).forEach(function (aff) {
      var affId = "f:" + aff;
      if (!affNodes[aff]) {
        var short = aff.split(",")[0].trim();
        affNodes[aff] = {
          id: affId, type: "affiliation",
          label: short.length > 30 ? short.slice(0, 30) + "\u2026" : short,
          full: aff
        };
      }
      _addUniq(affsByAuthor, auId,  affId);
      _addUniq(authorsByAff, affId, auId);
    });
  });
});

var edgeSet  = {};
var allEdges = [];
function _addEdge(src, tgt) {
  var k = src + "|" + tgt;
  if (!edgeSet[k]) { edgeSet[k] = true; allEdges.push({ source: src, target: tgt }); }
}
DATA.forEach(function (d) {
  var absId = "a:" + d.fileTitle;
  (d.authorDetails || []).forEach(function (au) {
    var auId = "u:" + au.name;
    _addEdge(auId, absId);
    (au.affs || []).forEach(function (aff) { _addEdge(auId, "f:" + aff); });
  });
});

// ── 2. Visible-set computation ───────────────────────────────────────────────

function getVisibleSet(focalId, dist) {
  var vis    = {};
  vis[focalId] = true;
  var prefix = focalId.slice(0, 2);

  if (prefix === "u:") {
    var auAbs = abstractsByAuthor[focalId] || [];
    var auAff = affsByAuthor[focalId]      || [];
    auAbs.forEach(function (id) { vis[id] = true; });
    auAff.forEach(function (id) { vis[id] = true; });
    if (dist >= 2) {
      auAbs.forEach(function (absId) {
        (authorsByAbstract[absId] || []).forEach(function (coId) { vis[coId] = true; });
      });
    }
    if (dist >= 3) {
      auAff.forEach(function (affId) {
        (authorsByAff[affId] || []).forEach(function (shId) { vis[shId] = true; });
      });
    }
    if (dist >= 4) {
      auAbs.forEach(function (absId) {
        (authorsByAbstract[absId] || []).forEach(function (coId) {
          if (coId !== focalId)
            (affsByAuthor[coId] || []).forEach(function (affId) { vis[affId] = true; });
        });
      });
    }

  } else if (prefix === "a:") {
    var absAu = authorsByAbstract[focalId] || [];
    absAu.forEach(function (auId) {
      vis[auId] = true;
      (affsByAuthor[auId] || []).forEach(function (affId) { vis[affId] = true; });
    });
    if (dist >= 2) {
      absAu.forEach(function (auId) {
        (abstractsByAuthor[auId] || []).forEach(function (id) { vis[id] = true; });
      });
    }
    if (dist >= 3) {
      Object.keys(vis).forEach(function (id) {
        if (id.slice(0, 2) === "a:")
          (authorsByAbstract[id] || []).forEach(function (auId) { vis[auId] = true; });
      });
    }
    if (dist >= 4) {
      Object.keys(vis).forEach(function (id) {
        if (id.slice(0, 2) === "u:")
          (affsByAuthor[id] || []).forEach(function (affId) { vis[affId] = true; });
      });
    }

  } else {
    var affAu = authorsByAff[focalId] || [];
    affAu.forEach(function (auId) { vis[auId] = true; });
    if (dist >= 2) {
      affAu.forEach(function (auId) {
        (abstractsByAuthor[auId] || []).forEach(function (id) { vis[id] = true; });
        (affsByAuthor[auId]      || []).forEach(function (id) { vis[id] = true; });
      });
    }
    if (dist >= 3) {
      Object.keys(vis).forEach(function (id) {
        if (id.slice(0, 2) === "a:")
          (authorsByAbstract[id] || []).forEach(function (auId) { vis[auId] = true; });
      });
    }
    if (dist >= 4) {
      Object.keys(vis).forEach(function (id) {
        if (id.slice(0, 2) === "u:")
          (affsByAuthor[id] || []).forEach(function (affId) { vis[affId] = true; });
      });
    }
  }
  return vis;
}

// ── 3. Initialise Cytoscape ───────────────────────────────────────────────────

var cyNodes = [];
Object.values(authorNodes).forEach(function (n) {
  cyNodes.push({ data: { id: n.id, type: n.type, label: n.label } });
});
Object.values(abstractNodes).forEach(function (n) {
  cyNodes.push({ data: { id: n.id, type: n.type, label: n.label,
    title: n.title, year: n.year, contact: n.contact,
    keywords: n.keywords, fileTitle: n.fileTitle } });
});
Object.values(affNodes).forEach(function (n) {
  cyNodes.push({ data: { id: n.id, type: n.type, label: n.label, full: n.full } });
});
var cyEdges = allEdges.map(function (e, i) {
  return { data: { id: "e" + i, source: e.source, target: e.target } };
});

var cy = cytoscape({
  container: document.getElementById("cy"),
  elements:  cyNodes.concat(cyEdges),
  style: [
    { selector: "node[type='author']", style: {
        "background-color": "#4A90D9", "color": "#fff",
        "label": "data(label)", "font-size": "10px",
        "text-valign": "center", "text-halign": "center",
        "shape": "round-rectangle", "padding": "8px",
        "width": "label", "height": "label",
        "text-wrap": "wrap", "text-max-width": "100px"
    }},
    { selector: "node[type='abstract']", style: {
        "background-color": "#E8A838", "color": "#fff",
        "label": "data(label)", "font-size": "9px",
        "text-valign": "center", "text-halign": "center",
        "shape": "round-rectangle", "padding": "7px",
        "width": "label", "height": "label",
        "text-wrap": "wrap", "text-max-width": "120px"
    }},
    { selector: "node[type='affiliation']", style: {
        "background-color": "#5BAD6F", "color": "#fff",
        "label": "data(label)", "font-size": "9px",
        "text-valign": "center", "text-halign": "center",
        "shape": "ellipse", "padding": "8px",
        "width": "label", "height": "label",
        "text-wrap": "wrap", "text-max-width": "100px"
    }},
    { selector: "node.focal", style: {
        "border-width": 3, "border-color": "#111", "border-opacity": 1
    }},
    { selector: "edge", style: {
        "width": 1.5, "line-color": "#ccc", "curve-style": "bezier", "opacity": 0.7
    }},
    { selector: ".kg-hidden", style: { "display": "none" }}
  ],
  layout: { name: "preset", fit: false }
});

cy.nodes().addClass("kg-hidden");
cy.edges().addClass("kg-hidden");

// ── 4. setFocalNode ───────────────────────────────────────────────────────────

var currentFocal = null;
var currentDist  = 1;

function setFocalNode(focalId, dist) {
  currentFocal = focalId;
  currentDist  = dist;
  var vis = getVisibleSet(focalId, dist);

  cy.batch(function () {
    cy.nodes().forEach(function (n) {
      if (vis[n.id()]) n.removeClass("kg-hidden"); else n.addClass("kg-hidden");
      n.removeClass("focal");
    });
    cy.edges().forEach(function (e) {
      if (vis[e.source().id()] && vis[e.target().id()])
        e.removeClass("kg-hidden");
      else
        e.addClass("kg-hidden");
    });
    cy.$id(focalId).addClass("focal");
  });

  cy.elements(":not(.kg-hidden)").layout({
    name: "cose", animate: true, animationDuration: 300,
    randomize: false, fit: true, padding: 20,
    nodeRepulsion: function () { return 25000; },
    idealEdgeLength: function () { return 160; },
    nodeOverlap: 20,
    numIter: 200,          // default is 2500 — 200 is plenty for these graph sizes
    initialTemp: 200,
    coolingFactor: 0.95,
    minTemp: 1.0
  }).run();

  document.querySelectorAll(".dist-btn").forEach(function (btn) {
    btn.classList.toggle("active", parseInt(btn.dataset.dist) === dist);
  });
}

// ── 5. Detail panel ───────────────────────────────────────────────────────────

function esc(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function showDetail(nodeId, data) {
  document.getElementById("detail-hint").style.display    = "none";
  document.getElementById("detail-content").style.display = "block";
  var badge = document.getElementById("detail-badge");
  badge.className   = "detail-badge type-" + data.type;
  badge.textContent = data.type;
  var bodyEl = document.getElementById("detail-body");
  var html   = "";

  if (data.type === "author") {
    document.getElementById("detail-title").textContent = data.label;
    var absIds = abstractsByAuthor[nodeId] || [];
    var affIds = affsByAuthor[nodeId]      || [];
    if (absIds.length) {
      html += "<div class='detail-section'><b>Abstracts:</b> " +
        absIds.map(function (id) {
          var nd = cy.$id(id).data();
          return "<a href='#' class='dl' data-id='" + esc(id) + "'>" + esc(nd.label) + "</a>";
        }).join(" &middot; ") + "</div>";
    }
    if (affIds.length) {
      html += "<div class='detail-section'><b>Affiliations:</b> " +
        affIds.map(function (id) {
          var nd = cy.$id(id).data();
          return "<a href='#' class='dl' data-id='" + esc(id) + "'>" + esc(nd.full || nd.label) + "</a>";
        }).join(" &middot; ") + "</div>";
    }

  } else if (data.type === "abstract") {
    document.getElementById("detail-title").textContent = data.title || data.label;
    var auIds = authorsByAbstract[nodeId] || [];
    if (data.year) html += "<div class='detail-section'><b>Year:</b> " + esc(data.year) + "</div>";
    if (auIds.length) {
      html += "<div class='detail-section'><b>Authors:</b> " +
        auIds.map(function (id) {
          var nd = cy.$id(id).data();
          return "<a href='#' class='dl' data-id='" + esc(id) + "'>" + esc(nd.label) + "</a>";
        }).join(", ") + "</div>";
    }
    if (data.keywords) html += "<div class='detail-section'><b>Keywords:</b> " + esc(data.keywords) + "</div>";
    if (data.fileTitle) {
      html += "<div class='detail-section'><a href='./reader.html?id=" +
              encodeURIComponent(data.fileTitle) + "' target='_blank'>Read abstract \u2197</a></div>";
    }

  } else {
    document.getElementById("detail-title").textContent = data.full || data.label;
    var auIds2 = authorsByAff[nodeId] || [];
    if (auIds2.length) {
      html += "<div class='detail-section'><b>Authors (" + auIds2.length + "):</b> " +
        auIds2.map(function (id) {
          var nd = cy.$id(id).data();
          return "<a href='#' class='dl' data-id='" + esc(id) + "'>" + esc(nd.label) + "</a>";
        }).join(", ") + "</div>";
    }
  }

  bodyEl.innerHTML = html;
  bodyEl.querySelectorAll("a.dl").forEach(function (a) {
    a.addEventListener("click", function (ev) {
      ev.preventDefault();
      var id = this.dataset.id;
      var nd = cy.$id(id).data();
      if (nd.type === "author") setFocalNode(id, currentDist);
      showDetail(id, nd);
    });
  });
}

// ── 6. Tap handler ────────────────────────────────────────────────────────────

cy.on("tap", "node", function (e) {
  var node = e.target;
  if (node.data("type") === "author") setFocalNode(node.id(), currentDist);
  showDetail(node.id(), node.data());
});

// ── 7. Distance buttons ───────────────────────────────────────────────────────

document.querySelectorAll(".dist-btn").forEach(function (btn) {
  btn.addEventListener("click", function () {
    if (currentFocal) setFocalNode(currentFocal, parseInt(btn.dataset.dist));
  });
});

// ── 8. Search ─────────────────────────────────────────────────────────────────

var searchMode   = "author";
var fuseAuthor   = new Fuse(Object.values(authorNodes),   { keys: ["label"],        threshold: 0.35, ignoreLocation: true });
var fuseAbstract = new Fuse(Object.values(abstractNodes), { keys: ["title"],        threshold: 0.35, ignoreLocation: true });
var fuseAff      = new Fuse(Object.values(affNodes),      { keys: ["full","label"], threshold: 0.35, ignoreLocation: true });
var qEl          = document.getElementById("q");
var clearEl      = document.getElementById("clear");
var suggestEl    = document.getElementById("suggestions");

function doSearch() {
  var q = qEl.value.trim();
  clearEl.style.display = q ? "block" : "none";
  if (!q) { suggestEl.innerHTML = ""; return; }
  var results = (searchMode === "author" ? fuseAuthor :
                 searchMode === "abstract" ? fuseAbstract : fuseAff).search(q).slice(0, 6);
  suggestEl.innerHTML = results.map(function (r) {
    var d = r.item;
    var text = (searchMode === "abstract") ? (d.title || d.label) : (d.full || d.label);
    return "<div class='suggestion' data-id='" + esc(d.id) + "'>" + esc(text) + "</div>";
  }).join("");
  suggestEl.querySelectorAll(".suggestion").forEach(function (el) {
    el.addEventListener("click", function () {
      var id = this.dataset.id;
      setFocalNode(id, 1);
      showDetail(id, cy.$id(id).data());
      qEl.value = ""; clearEl.style.display = "none"; suggestEl.innerHTML = "";
    });
  });
}

qEl.addEventListener("input", doSearch);
clearEl.addEventListener("click", function () {
  qEl.value = ""; clearEl.style.display = "none"; suggestEl.innerHTML = "";
});
document.addEventListener("click", function (ev) {
  if (!ev.target.closest("#search-wrap")) suggestEl.innerHTML = "";
});
document.querySelectorAll(".mode-btn").forEach(function (btn) {
  btn.addEventListener("click", function () {
    document.querySelectorAll(".mode-btn").forEach(function (b) { b.classList.remove("active"); });
    btn.classList.add("active");
    searchMode      = btn.dataset.mode;
    qEl.placeholder = "Search " + searchMode + "s\u2026";
    doSearch();
  });
});

// ── 9. Random initial author ──────────────────────────────────────────────────

var authorNames = Object.keys(authorNodes);
if (authorNames.length) {
  var seedName = authorNames[Math.floor(Math.random() * authorNames.length)];
  var seedId   = authorNodes[seedName].id;
  setFocalNode(seedId, 1);
  showDetail(seedId, cy.$id(seedId).data());
}

}());
</script>
</body>
</html>"""


def _kg_html(entries: list) -> str:
    """Return self-contained knowledge graph HTML (Cytoscape.js + Fuse.js)."""
    data_json = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")
    return (_KG_TEMPLATE
            .replace("__LOGO_HTML__", _logo_html())
            .replace("__DATA_JSON__", data_json))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found.")
        sys.exit(1)

    with open(DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    entries = [flatten(e) for e in raw if isinstance(e, dict)]
    print(f"Flattened {len(entries)} entries.")

    # Serialise — escape </ to prevent accidental script-tag closing
    data_json = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")

    WIDGETS_DIR.mkdir(parents=True, exist_ok=True)

    # (fname, page_title, css, row_js, extra_js, extra_html)
    specs = [
        ("search_option_1.html", "Katalytikertagung \u2013 Abstract Search (Compact)",
         _OPT1_CSS, _OPT1_ROW, "", ""),
        ("search_option_2.html", "Katalytikertagung \u2013 Abstract Search (Accordion)",
         _OPT2_CSS, _OPT2_ROW, _OPT2_EXTRA_JS, ""),
        ("search_option_3.html", "Katalytikertagung \u2013 Abstract Search (Full Details)",
         _OPT3_CSS, _OPT3_ROW, "", ""),
        ("search_option_4.html",
         "Katalytikertagung \u2013 Abstract Search (Compact Accordion)",
         _OPT4_CSS, _OPT4_ROW, _OPT4_EXTRA_JS, ""),
        ("search_option_5.html",
         "Katalytikertagung \u2013 Abstract Search and Display",
         _OPT5_CSS, _OPT5_ROW, _OPT5_EXTRA_JS, _OPT5_HTML),
    ]

    for fname, title, css, row_js, extra_js, extra_html in specs:
        html = (_assemble(title, css, row_js, extra_js, extra_html)
                .replace("__DATA_JSON__", data_json))
        out = WIDGETS_DIR / fname
        out.write_text(html, encoding="utf-8")
        print(f"  {out.name}  ({out.stat().st_size // 1024} KB)")

    # Reader page
    reader = _reader_html().replace("__DATA_JSON__", data_json)
    reader_out = WIDGETS_DIR / "reader.html"
    reader_out.write_text(reader, encoding="utf-8")
    print(f"  {reader_out.name}  ({reader_out.stat().st_size // 1024} KB)")

    # Knowledge Graph
    kg_out = WIDGETS_DIR / "knowledge_graph.html"
    kg_out.write_text(_kg_html(entries), encoding="utf-8")
    print(f"  {kg_out.name}  ({kg_out.stat().st_size // 1024} KB)")

    # Backward-compat copy
    LEGACY_OUT.write_text(
        (WIDGETS_DIR / "search_option_1.html").read_text(encoding="utf-8"),
        encoding="utf-8")
    print(f"  search_widget/index.html  (updated)")


if __name__ == "__main__":
    main()
