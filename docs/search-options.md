# Search Widget – Embed Options

Three variants of the search widget are available, each self-contained HTML file
served via GitHub Pages.  Choose the one that fits your website context and embed
it with the `<iframe>` code shown below.

---

## Option 1 — Compact

A minimal two-line result row: bold title + year on the first line, presenting
author and truncated co-author list on the second line.

**Best for:** tight spaces, sidebars, or pages where brevity is important.

**Preview:**

<iframe
  src="widgets/search_option_1.html"
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
  src="widgets/search_option_2.html"
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
  src="widgets/search_option_3.html"
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

## Comparison

| | Option 1 | Option 2 | Option 3 |
|---|---|---|---|
| Title + year | ✓ | ✓ | ✓ |
| Presenting author | truncated | ✓ | ✓ |
| Full author list | truncated | on expand | ✓ |
| Affiliations | truncated | on expand | ✓ |
| PDF reader link | — | — | ✓ |
| Recommended height | 440 px | 440 px | 520 px |

---

## Updating the widget

After approving new abstracts in the review GUI, regenerate all widget files:

```bash
py search_widget/build.py
```

Then commit and push — GitHub Pages updates within seconds.
