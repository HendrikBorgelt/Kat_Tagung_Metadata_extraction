"""
build.py  —  Generate all search widget variants from data/abstract_metadata.json.

Outputs (all self-contained HTML, no backend required):
  docs/widgets/search_option_1.html  — compact, one-line author row
  docs/widgets/search_option_2.html  — accordion: click row to expand details
  docs/widgets/search_option_3.html  — full details + "Read abstract" PDF link
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
LOGO_PATH   = _ROOT / "assets" / "Dechema_und_NFDI4Cat_logo.png"
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
      padding: 10px 12px 7px; border-bottom: 1px solid #e0e0e0; flex-shrink: 0;
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
              render_row_js: str, extra_js: str = "") -> str:
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
{footer}
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

    specs = [
        ("search_option_1.html", "Katalytikertagung \u2013 Abstract Search (Compact)",
         _OPT1_CSS, _OPT1_ROW, ""),
        ("search_option_2.html", "Katalytikertagung \u2013 Abstract Search (Accordion)",
         _OPT2_CSS, _OPT2_ROW, _OPT2_EXTRA_JS),
        ("search_option_3.html", "Katalytikertagung \u2013 Abstract Search (Full Details)",
         _OPT3_CSS, _OPT3_ROW, ""),
    ]

    for fname, title, css, row_js, extra_js in specs:
        html = (_assemble(title, css, row_js, extra_js)
                .replace("__DATA_JSON__", data_json))
        out = WIDGETS_DIR / fname
        out.write_text(html, encoding="utf-8")
        print(f"  {out.name}  ({out.stat().st_size // 1024} KB)")

    # Reader page
    reader = _reader_html().replace("__DATA_JSON__", data_json)
    reader_out = WIDGETS_DIR / "reader.html"
    reader_out.write_text(reader, encoding="utf-8")
    print(f"  {reader_out.name}  ({reader_out.stat().st_size // 1024} KB)")

    # Backward-compat copy
    LEGACY_OUT.write_text(
        (WIDGETS_DIR / "search_option_1.html").read_text(encoding="utf-8"),
        encoding="utf-8")
    print(f"  search_widget/index.html  (updated)")


if __name__ == "__main__":
    main()
