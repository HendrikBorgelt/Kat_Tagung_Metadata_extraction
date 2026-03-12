# Search Widget – Embed Options

Six variants of the search widget are available, each a self-contained HTML file
served via GitHub Pages.  Choose the one that fits your website context and embed
it with the `<iframe>` code shown below.

---

## Option 1 — Compact

A minimal two-line result row: bold title + year on the first line, presenting
author and truncated co-author list on the second line.

**Best for:** tight spaces, sidebars, or pages where brevity is important.

**Preview:**

<iframe
  src="../widgets/search_option_1.html"
  width="100%"
  height="440"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px; margin-bottom:12px;">
</iframe>

**Embed code:**
```html
<iframe
  src="https://hendrikborgelt.github.io/Kat_Tagung_Metadata_extraction/widgets/search_option_1.html"
  width="100%"
  height="440"
  frameborder="0">
</iframe>
```

---

## Option 2 — Accordion

Each result shows title + presenting author collapsed.  Click any row to expand
the full author list with affiliations.

**Best for:** pages where you want to keep the initial view compact but still
allow users to dig into author details without leaving the page.

**Preview:**

<iframe
  src="../widgets/search_option_2.html"
  width="100%"
  height="440"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px; margin-bottom:12px;">
</iframe>

**Embed code:**
```html
<iframe
  src="https://hendrikborgelt.github.io/Kat_Tagung_Metadata_extraction/widgets/search_option_2.html"
  width="100%"
  height="440"
  frameborder="0">
</iframe>
```

---

## Option 3 — Full Details + PDF Reader

Each result shows title, presenting author, full author list with institutions,
and a **Read abstract →** button that opens the original PDF inline in a reader page.

**Best for:** the primary conference page where users should have full access to all
information and the ability to read the original abstract.

**Preview:**

<iframe
  src="../widgets/search_option_3.html"
  width="100%"
  height="520"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px; margin-bottom:12px;">
</iframe>

**Embed code:**
```html
<iframe
  src="https://hendrikborgelt.github.io/Kat_Tagung_Metadata_extraction/widgets/search_option_3.html"
  width="100%"
  height="520"
  frameborder="0">
</iframe>
```

---

## Option 4 — Compact Accordion + PDF Link

Titles are collapsed by default.  Click any row to expand the full author list
with affiliations indented beneath each author name, plus keywords and
references where available.  The presenting author and **Read abstract →** button
are always visible without expanding.

**Best for:** embedding in tight spaces (sidebar, page column) where you still
want full detail on demand and quick access to the PDF.
Recommended at **50 % width** and **300 px height**.

**Preview (shown at 50 % width):**

<div style="width:50%">
<iframe
  src="../widgets/search_option_4.html"
  width="100%"
  height="340"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px; margin-bottom:12px;">
</iframe>
</div>

**Embed code (50 % width, standalone):**
```html
<iframe
  src="https://hendrikborgelt.github.io/Kat_Tagung_Metadata_extraction/widgets/search_option_4.html"
  width="50%"
  height="300"
  frameborder="0">
</iframe>
```

**Embed code — linked two-iframe layout (search + inline PDF viewer):**

Place both iframes side-by-side.  When the user clicks **Read abstract →** inside
the search widget, the reader page loads in the PDF iframe on the same page
instead of opening a new tab.  This uses the
[`postMessage` API](https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage)
— no server or shared secret required.

```html
<div style="display:flex; gap:12px; height:600px;">
  <!-- Search widget (left) -->
  <iframe
    id="search-frame"
    src="https://hendrikborgelt.github.io/Kat_Tagung_Metadata_extraction/widgets/search_option_4.html"
    width="50%"
    height="100%"
    frameborder="0"
    style="border:1px solid #e0e0e0; border-radius:4px;">
  </iframe>

  <!-- PDF / reader pane (right, starts empty) -->
  <iframe
    id="pdf-frame"
    src="about:blank"
    width="50%"
    height="100%"
    frameborder="0"
    style="border:1px solid #e0e0e0; border-radius:4px;">
  </iframe>
</div>

<script>
window.addEventListener("message", function (e) {
  // Only accept messages from the GitHub Pages widget origin
  if (e.origin !== "https://hendrikborgelt.github.io") return;
  if (e.data && e.data.type === "katTagung_openReader") {
    document.getElementById("pdf-frame").src = e.data.url;
  }
});
</script>
```

---

## Option 5 — Search and Display Box

A single all-in-one widget: the search bar, collapsible results, and an inline
PDF reader all live inside one iframe.  Clicking **Read abstract →** on any
result opens the PDF and author metadata directly below the results list —
no new tab, no second iframe needed.

The widget automatically notifies the parent page to resize itself from
**340 px** (search only) to **800 px** (search + PDF) using `postMessage`.
Add a CSS transition on the iframe for a smooth animated expansion.

**Best for:** conference pages where you want one self-contained block that
handles everything — search, browse, and read — without any extra plumbing.

**Preview** *(click "Read abstract →" on any row to see the reader expand):*

<iframe
  src="../widgets/search_option_5.html"
  width="100%"
  height="340"
  id="opt5-preview"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px; margin-bottom:4px;
         transition: height 0.4s ease;">
</iframe>
<script>
window.addEventListener("message", function(e) {
  if (e.data && e.data.type === "katTagung_resize") {
    var f = document.getElementById("opt5-preview");
    if (f) f.style.height = e.data.height + "px";
  }
});
</script>

**Embed code (auto-resizing):**
```html
<iframe
  id="search-display"
  src="https://hendrikborgelt.github.io/Kat_Tagung_Metadata_extraction/widgets/search_option_5.html"
  width="100%"
  height="340"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px;
         transition: height 0.4s ease;">
</iframe>

<script>
window.addEventListener("message", function (e) {
  if (e.origin !== "https://hendrikborgelt.github.io") return;
  if (e.data && e.data.type === "katTagung_resize") {
    document.getElementById("search-display").style.height = e.data.height + "px";
  }
});
</script>
```

---

## Knowledge Graph

An interactive semantic knowledge graph showing relationships between authors,
abstracts, and affiliations.  A random author is shown on load — use the search
bar to navigate to any author, abstract, or affiliation, and the **Distance**
buttons to expand the visible neighbourhood:

| Distance | What is shown |
|---|---|
| **1** | Focal author + their abstracts + their affiliations |
| **2** | + co-authors of those abstracts |
| **3** | + all authors sharing the focal author's affiliations |
| **4** | + affiliations of the distance-2 co-authors |

Click any author node in the graph to make it the new focal point.
Click abstract or affiliation nodes to see their details in the panel below.

**Node colours:** <span style="color:#4A90D9">■</span> Author &nbsp;
<span style="color:#E8A838">■</span> Abstract &nbsp;
<span style="color:#5BAD6F">■</span> Affiliation

**Preview:**

<iframe
  src="../widgets/knowledge_graph.html"
  width="100%"
  height="680"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px; margin-bottom:12px;">
</iframe>

**Embed code:**
```html
<iframe
  src="https://hendrikborgelt.github.io/Kat_Tagung_Metadata_extraction/widgets/knowledge_graph.html"
  width="100%"
  height="680"
  frameborder="0"
  style="border:1px solid #e0e0e0; border-radius:4px;">
</iframe>
```

---

## Comparison

| | Option 1 | Option 2 | Option 3 | Option 4 | Option 5 | KG |
|---|---|---|---|---|---|---|
| Title + year | ✓ | ✓ | ✓ | ✓ | ✓ | via detail panel |
| Presenting author | truncated | ✓ | ✓ | always visible | always visible | via detail panel |
| Full author list | truncated | on expand | ✓ | on expand | on expand | graph nodes |
| Affiliations | truncated | on expand | ✓ | indented, on expand | indented, on expand | graph nodes |
| Keywords | — | — | — | on expand | on expand | via detail panel |
| References | — | — | — | on expand | on expand | — |
| PDF reader | external tab | — | external tab | external tab | **inline** | external tab |
| Auto-resize iframe | — | — | — | — | ✓ (340 → 800 px) | — |
| Recommended width | 100 % | 100 % | 100 % | 50 % | 100 % | 100 % |
| Initial height | 440 px | 440 px | 520 px | 300 px | 340 px | 680 px |

---

## Updating the widget

After approving new abstracts in the review GUI, regenerate all widget files:

```bash
py search_widget/build.py
```

Then commit and push — GitHub Pages updates within seconds.
