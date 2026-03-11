"""
2_review_gui.py  —  Review/approve staged abstracts; manage approved metadata.

Usage:
    py scripts/pipeline/2_review_gui.py

Modes (toggle via toolbar):
  Staged   – review entries from staging.json
             full metadata edit + affiliation decision widgets
             actions: Approve / Discard / Skip
  Approved – browse entries from abstract_metadata.json
             full metadata edit + save
             actions: Save / Delete

Granular deletion is supported at every level:
  whole abstract · individual author · individual affiliation · relation string
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from pathlib import Path

# ── add repo root to path ─────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import shared

# ── optional heavy imports ────────────────────────────────────────────────────
try:
    from PIL import Image, ImageTk      # pip install pillow
    _PIL = True
except ImportError:
    _PIL = False

try:
    import fitz                          # pip install pymupdf
    _FITZ = True
except ImportError:
    _FITZ = False


# ═════════════════════════════════════════════════════════════════════════════
# Utility: vertical scrollable frame
# ═════════════════════════════════════════════════════════════════════════════

class ScrollableFrame(ttk.Frame):
    """Vertical-scroll container.  Place children inside `.inner`."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.inner = ttk.Frame(self._canvas)
        self._win = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner)
        self._canvas.bind("<Configure>", self._on_canvas)
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner(self, _e=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas(self, _e=None):
        self._canvas.itemconfig(self._win, width=self._canvas.winfo_width())

    def _bind_wheel(self, _e=None):
        self._canvas.bind_all("<MouseWheel>", self._wheel)

    def _unbind_wheel(self, _e=None):
        self._canvas.unbind_all("<MouseWheel>")

    def _wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ═════════════════════════════════════════════════════════════════════════════
# Affiliation decision widget  (staged mode only)
# ═════════════════════════════════════════════════════════════════════════════

class AffDecisionWidget(ttk.Frame):
    """
    Displays one raw affiliation string + radio buttons:
      [Existing: <combobox>  score] [New: <entry>]  [Revert]
    Updates the decision record (a dict from _aff_decisions) in-place.
    """

    def __init__(self, parent, rec: dict, registry: dict, on_remove=None, **kw):
        super().__init__(parent, relief="groove", padding=(4, 2), **kw)
        self._rec = rec
        self._registry = registry
        self._on_remove = on_remove
        # Freeze original decision for Revert
        self._orig_decision  = rec.get("decision", "pending")
        self._orig_canonical = rec.get("matched_canonical") or ""
        self._build()

    def _build(self):
        raw   = self._rec.get("raw", "")
        score = self._rec.get("match_score", 0.0)
        matched = self._rec.get("matched_canonical") or ""

        # ── row 0: raw label + remove button ─────────────────────────────
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text=f"Raw: {raw}", foreground="#555555",
                  wraplength=300, justify="left").pack(side="left", fill="x", expand=True)
        if self._on_remove:
            ttk.Button(top, text="x", width=2,
                       command=self._on_remove).pack(side="right")

        # ── radio variable ────────────────────────────────────────────────
        orig = self._orig_decision
        init_val = ("existing" if orig == "auto_existing" else
                    "new"      if orig == "auto_new"      else "")
        self._var = tk.StringVar(value=init_val)

        # ── row 1: existing radio + combobox + score ──────────────────────
        row_ex = ttk.Frame(self)
        row_ex.pack(fill="x", pady=1)
        ttk.Radiobutton(row_ex, text="Existing:",
                        variable=self._var, value="existing",
                        command=self._on_radio).pack(side="left")
        self._exist_var = tk.StringVar(value=matched)
        self._cb = ttk.Combobox(row_ex, textvariable=self._exist_var, width=34)
        self._cb["values"] = sorted(self._registry.keys())[:200]
        self._cb.pack(side="left", padx=2)
        self._cb.bind("<<ComboboxSelected>>", self._on_combo)
        self._cb.bind("<KeyRelease>",          self._filter_cb)
        ttk.Label(row_ex, text=f"[{score:.2f}]",
                  foreground="#888888").pack(side="left")

        # ── row 2: new radio + entry ──────────────────────────────────────
        row_new = ttk.Frame(self)
        row_new.pack(fill="x", pady=1)
        ttk.Radiobutton(row_new, text="New:     ",
                        variable=self._var, value="new",
                        command=self._on_radio).pack(side="left")
        default_new = self._rec.get("new_canonical") or raw
        self._new_var = tk.StringVar(value=default_new)
        ttk.Entry(row_new, textvariable=self._new_var,
                  width=36).pack(side="left", padx=2)
        self._new_var.trace_add("write", self._on_new_edit)

        # ── row 3: revert button ──────────────────────────────────────────
        row_rev = ttk.Frame(self)
        row_rev.pack(fill="x")
        ttk.Button(row_rev, text="Revert", width=6,
                   command=self._revert).pack(side="right")

    # ── event handlers ────────────────────────────────────────────────────

    def _on_radio(self):
        v = self._var.get()
        self._rec["decision"] = v
        if v == "existing":
            self._rec["matched_canonical"] = self._exist_var.get()
        elif v == "new":
            self._rec["new_canonical"] = self._new_var.get()

    def _on_combo(self, _e=None):
        self._rec["matched_canonical"] = self._exist_var.get()
        self._var.set("existing")
        self._rec["decision"] = "existing"

    def _filter_cb(self, _e=None):
        q = self._exist_var.get().lower()
        self._cb["values"] = sorted(
            c for c in self._registry if q in c.lower())[:100]

    def _on_new_edit(self, *_):
        self._rec["new_canonical"] = self._new_var.get()
        self._var.set("new")
        self._rec["decision"] = "new"

    def _revert(self):
        orig = self._orig_decision
        if orig == "auto_existing":
            self._var.set("existing")
            self._exist_var.set(self._orig_canonical)
            self._rec.update(decision="existing", matched_canonical=self._orig_canonical)
        elif orig == "auto_new":
            raw = self._rec.get("raw", "")
            self._var.set("new")
            self._new_var.set(raw)
            self._rec.update(decision="new", new_canonical=raw)
        else:   # pending
            self._var.set("")
            self._exist_var.set(self._orig_canonical)
            self._rec["decision"] = "pending"

    def is_decided(self) -> bool:
        return self._var.get() in ("existing", "new")


# ═════════════════════════════════════════════════════════════════════════════
# Author widget
# ═════════════════════════════════════════════════════════════════════════════

class AuthorWidget(ttk.LabelFrame):
    """
    Displays one author: name entry + list of affiliation rows.
    In staged mode each affiliation shows an AffDecisionWidget.
    In approved mode each affiliation is a plain editable entry.
    """

    def __init__(self, parent, author: dict, aff_decisions: list,
                 registry: dict, staged: bool, on_remove=None, **kw):
        label = author.get("name", "Author")
        super().__init__(parent, text=label, padding=4, **kw)
        self._author       = author
        self._aff_decisions = aff_decisions
        self._registry     = registry
        self._staged       = staged
        self._on_remove    = on_remove
        self._aff_widgets: list = []
        self._build()

    def _build(self):
        # Header row: name entry + remove button
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", pady=(0, 2))
        ttk.Label(hdr, text="Name:").pack(side="left")
        self._name_var = tk.StringVar(value=self._author.get("name", ""))
        ttk.Entry(hdr, textvariable=self._name_var,
                  width=24).pack(side="left", padx=4)
        self._name_var.trace_add("write", self._on_name_change)
        if self._on_remove:
            ttk.Button(hdr, text="Remove author", width=13,
                       command=self._on_remove).pack(side="right")

        # Affiliation container
        self._aff_container = ttk.Frame(self)
        self._aff_container.pack(fill="x")
        self._rebuild_affs()

        ttk.Button(self, text="+ Add affiliation",
                   command=self._add_aff).pack(anchor="w", pady=2)

    # ── affiliations ──────────────────────────────────────────────────────

    def _rebuild_affs(self):
        for w in self._aff_widgets:
            w.destroy()
        self._aff_widgets.clear()

        affs = self._author.get("affiliations", [])
        for i, aff in enumerate(affs):
            def make_remove(idx=i, raw_aff=aff):
                def _remove():
                    a = self._author.get("affiliations", [])
                    if idx < len(a):
                        a.pop(idx)
                    cur_name = self._author.get("name", "")
                    self._aff_decisions[:] = [
                        r for r in self._aff_decisions
                        if not (r.get("author") == cur_name
                                and r.get("raw") == raw_aff)
                    ]
                    self._rebuild_affs()
                return _remove

            if self._staged:
                rec = self._get_or_create_decision(
                    self._author.get("name", ""), aff)
                w = AffDecisionWidget(
                    self._aff_container, rec, self._registry,
                    on_remove=make_remove(i, aff))
            else:
                # Approved mode: plain editable entry
                w = ttk.Frame(self._aff_container)
                var = tk.StringVar(value=aff)

                def make_updater(idx=i, v=var):
                    def _update(*_):
                        a = self._author.get("affiliations", [])
                        if idx < len(a):
                            a[idx] = v.get()
                    return _update

                var.trace_add("write", make_updater(i, var))
                ttk.Entry(w, textvariable=var,
                          width=44).pack(side="left", fill="x", expand=True)
                ttk.Button(w, text="x", width=2,
                           command=make_remove(i, aff)).pack(side="right")

            w.pack(fill="x", pady=1)
            self._aff_widgets.append(w)

    def _get_or_create_decision(self, author_name: str, raw: str) -> dict:
        """Return existing _aff_decision record or create one."""
        for rec in self._aff_decisions:
            if rec.get("author") == author_name and rec.get("raw") == raw:
                return rec
        canonical, score, decision = shared.match_affiliation(raw, self._registry)
        rec = {
            "author":            author_name,
            "raw":               raw,
            "matched_canonical": canonical,
            "match_score":       round(score, 4),
            "decision":          decision,
        }
        self._aff_decisions.append(rec)
        return rec

    def _add_aff(self):
        raw = simpledialog.askstring(
            "Add affiliation", "Enter affiliation string:",
            parent=self.winfo_toplevel())
        if raw and raw.strip():
            self._author.setdefault("affiliations", []).append(raw.strip())
            self._rebuild_affs()

    def _on_name_change(self, *_):
        new_name = self._name_var.get()
        old_name = self._author.get("name", "")
        if new_name == old_name:
            return
        for rec in self._aff_decisions:
            if rec.get("author") == old_name:
                rec["author"] = new_name
        self._author["name"] = new_name
        self.configure(text=new_name)

    def pending_decisions(self) -> int:
        """Count unresolved affiliation widgets (staged mode only)."""
        if not self._staged:
            return 0
        return sum(
            1 for w in self._aff_widgets
            if isinstance(w, AffDecisionWidget) and not w.is_decided()
        )


# ═════════════════════════════════════════════════════════════════════════════
# Main application
# ═════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    STAGED   = "staged"
    APPROVED = "approved"

    def __init__(self):
        super().__init__()
        self.title("Abstract Metadata Review")
        self.geometry("1440x860")
        self.minsize(960, 600)

        # State
        self._mode     = self.STAGED
        self._entries: list[dict]  = []
        self._filtered: list[dict] = []
        self._current: dict | None = None
        self._registry: dict       = {}
        self._pdf_doc              = None
        self._pdf_page             = 0
        self._photo                = None    # keep PIL reference alive

        # Widgets filled later
        self._author_widgets: list[AuthorWidget] = []
        self._field_vars: dict[str, tk.StringVar] = {}
        self._entry_authors: list       = []
        self._entry_aff_decisions: list = []
        self._entry_relations: list     = []

        self._registry = shared.load_registry()
        self._build_ui()
        self._populate_list()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar
        tb = ttk.Frame(self, padding=(4, 2))
        tb.pack(side="top", fill="x")
        self._btn_staged = ttk.Button(
            tb, text="(Staged)", width=12,
            command=lambda: self._set_mode(self.STAGED))
        self._btn_staged.pack(side="left", padx=2)
        self._btn_approved = ttk.Button(
            tb, text="Approved", width=12,
            command=lambda: self._set_mode(self.APPROVED))
        self._btn_approved.pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        self._status_var = tk.StringVar()
        ttk.Label(tb, textvariable=self._status_var,
                  foreground="#555555").pack(side="left")

        # Three-pane layout
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)

        left = ttk.Frame(pw)
        pw.add(left, weight=1)
        self._build_left(left)

        mid = ttk.Frame(pw)
        pw.add(mid, weight=2)
        self._build_mid(mid)

        right = ttk.Frame(pw)
        pw.add(right, weight=3)
        self._build_right(right)

    # ── left pane: entry list ─────────────────────────────────────────────────

    def _build_left(self, parent):
        ttk.Label(parent, text="Search:").pack(anchor="w", padx=4, pady=(4, 0))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_search())
        ttk.Entry(parent, textvariable=self._search_var).pack(
            fill="x", padx=4, pady=2)

        rf = ttk.Frame(parent)
        rf.pack(fill="x", padx=4)
        self._stype = tk.StringVar(value="title")
        for val, lbl in (("title", "Title"), ("author", "Author"),
                          ("affiliation", "Affil.")):
            ttk.Radiobutton(rf, text=lbl, variable=self._stype,
                            value=val,
                            command=self._apply_search).pack(side="left")

        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=4, pady=4)
        vsb = ttk.Scrollbar(frm, orient="vertical")
        self._listbox = tk.Listbox(
            frm, selectmode="single",
            yscrollcommand=vsb.set,
            font=("TkDefaultFont", 9),
            activestyle="dotbox")
        vsb.configure(command=self._listbox.yview)
        vsb.pack(side="right", fill="y")
        self._listbox.pack(side="left", fill="both", expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

    # ── middle pane: PDF viewer ───────────────────────────────────────────────

    def _build_mid(self, parent):
        nav = ttk.Frame(parent)
        nav.pack(fill="x", padx=4, pady=2)
        ttk.Button(nav, text="<", width=3,
                   command=self._pdf_prev).pack(side="left")
        self._page_var = tk.StringVar(value="Page -- / --")
        ttk.Label(nav, textvariable=self._page_var).pack(side="left", padx=6)
        ttk.Button(nav, text=">", width=3,
                   command=self._pdf_next).pack(side="left")

        # Vertical split: image (top) + text (bottom)
        vpw = ttk.PanedWindow(parent, orient="vertical")
        vpw.pack(fill="both", expand=True)

        img_f = ttk.Frame(vpw)
        vpw.add(img_f, weight=3)
        self._pdf_canvas = tk.Canvas(img_f, bg="#cccccc", cursor="crosshair")
        self._pdf_canvas.pack(fill="both", expand=True, padx=4, pady=2)
        self._pdf_canvas.bind("<Configure>", lambda _: self._render_pdf_page())

        txt_f = ttk.Frame(vpw)
        vpw.add(txt_f, weight=1)
        ttk.Label(txt_f,
                  text="PDF text (reference / copy-paste):").pack(
            anchor="w", padx=4, pady=(2, 0))
        f2 = ttk.Frame(txt_f)
        f2.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        tsb = ttk.Scrollbar(f2, orient="vertical")
        self._pdf_text = tk.Text(
            f2, yscrollcommand=tsb.set,
            state="disabled", wrap="word",
            font=("TkDefaultFont", 8))
        tsb.configure(command=self._pdf_text.yview)
        tsb.pack(side="right", fill="y")
        self._pdf_text.pack(side="left", fill="both", expand=True)

    # ── right pane: metadata editor ───────────────────────────────────────────

    def _build_right(self, parent):
        self._right_scroll = ScrollableFrame(parent)
        self._right_scroll.pack(fill="both", expand=True)
        self._right_inner = self._right_scroll.inner
        self._action_bar  = ttk.Frame(parent, padding=(4, 2))
        self._action_bar.pack(fill="x", side="bottom")

    # ── mode switching ────────────────────────────────────────────────────────

    def _set_mode(self, mode: str):
        self._mode = mode
        self._btn_staged.configure(
            text="(Staged)"  if mode == self.STAGED   else "Staged")
        self._btn_approved.configure(
            text="(Approved)" if mode == self.APPROVED else "Approved")
        self._clear_detail()
        self._populate_list()

    # ── entry list ────────────────────────────────────────────────────────────

    def _populate_list(self):
        if self._mode == self.STAGED:
            all_e = shared.load_json(shared.STAGING_PATH)
            self._entries = [e for e in all_e
                             if e.get("_status") in ("pending", "failed")]
        else:
            self._entries = shared.load_json(shared.METADATA_PATH)
        self._apply_search()

    def _apply_search(self, *_):
        q     = self._search_var.get().lower()
        stype = self._stype.get()

        if not q:
            self._filtered = list(self._entries)
        else:
            self._filtered = []
            for e in self._entries:
                if stype == "title":
                    hay = (e.get("dct:title", "") + " " +
                           e.get("file_title", "")).lower()
                elif stype == "author":
                    hay = " ".join(
                        a.get("name", "") for a in e.get("authors", [])).lower()
                else:   # affiliation
                    hay = " ".join(
                        aff
                        for a in e.get("authors", [])
                        for aff in a.get("affiliations", [])).lower()
                if q in hay:
                    self._filtered.append(e)

        self._listbox.delete(0, "end")
        for e in self._filtered:
            status = e.get("_status", "")
            n_pend = sum(1 for d in e.get("_aff_decisions", [])
                         if d.get("decision") == "pending")
            if status == "failed":
                icon = "[!]"
            elif n_pend:
                icon = f"[{n_pend}?]"
            else:
                icon = "[ok]"
            title = e.get("dct:title") or e.get("file_title", "(no title)")
            self._listbox.insert("end", f"{icon} {title[:55]}")

        mode_lbl = "Staged" if self._mode == self.STAGED else "Approved"
        self._status_var.set(
            f"{mode_lbl}: {len(self._entries)}  |  showing {len(self._filtered)}")

    def _on_select(self, _e=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._filtered):
            self._current = self._filtered[idx]
            self._show_detail(self._current)

    # ── PDF viewer ────────────────────────────────────────────────────────────

    def _show_pdf(self, file_title: str):
        self._close_pdf()
        path = shared.pdf_path_for(file_title)
        if not path:
            self._page_var.set("PDF not found")
            return
        if not _FITZ:
            self._page_var.set("pymupdf not installed")
            return
        try:
            self._pdf_doc  = fitz.open(str(path))
            self._pdf_page = 0
            self._render_pdf_page()
            pages_text = [p.get_text() for p in self._pdf_doc]
            full_text  = "\n\n--- page break ---\n\n".join(pages_text)
            self._pdf_text.config(state="normal")
            self._pdf_text.delete("1.0", "end")
            self._pdf_text.insert("end", full_text)
            self._pdf_text.config(state="disabled")
        except Exception as exc:
            self._page_var.set(f"Error: {exc}")

    def _render_pdf_page(self):
        if not self._pdf_doc:
            return
        n = len(self._pdf_doc)
        p = max(0, min(self._pdf_page, n - 1))
        self._pdf_page = p
        self._page_var.set(f"Page {p + 1} / {n}")
        page = self._pdf_doc[p]
        mat  = fitz.Matrix(1.5, 1.5)
        pix  = page.get_pixmap(matrix=mat)
        self._pdf_canvas.update_idletasks()
        cw = max(self._pdf_canvas.winfo_width(),  10)
        ch = max(self._pdf_canvas.winfo_height(), 10)
        if _PIL:
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.thumbnail((cw, ch), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self._pdf_canvas.delete("all")
            self._pdf_canvas.create_image(
                cw // 2, ch // 2, image=self._photo, anchor="center")
        else:
            self._pdf_canvas.delete("all")
            self._pdf_canvas.create_text(
                10, 10, anchor="nw",
                text="Install Pillow for PDF image preview\n(pip install pillow)",
                fill="#888888")

    def _pdf_prev(self):
        if self._pdf_doc and self._pdf_page > 0:
            self._pdf_page -= 1
            self._render_pdf_page()

    def _pdf_next(self):
        if self._pdf_doc and self._pdf_page < len(self._pdf_doc) - 1:
            self._pdf_page += 1
            self._render_pdf_page()

    def _close_pdf(self):
        if self._pdf_doc:
            try:
                self._pdf_doc.close()
            except Exception:
                pass
            self._pdf_doc = None
        self._pdf_canvas.delete("all")
        self._page_var.set("Page -- / --")
        self._pdf_text.config(state="normal")
        self._pdf_text.delete("1.0", "end")
        self._pdf_text.config(state="disabled")

    # ── metadata panel ────────────────────────────────────────────────────────

    def _show_detail(self, entry: dict):
        self._clear_detail()
        self._show_pdf(entry.get("file_title", ""))
        self._build_detail(entry)

    def _clear_detail(self):
        for w in self._right_inner.winfo_children():
            w.destroy()
        for w in self._action_bar.winfo_children():
            w.destroy()
        self._author_widgets.clear()
        self._close_pdf()

    def _build_detail(self, entry: dict):
        inner  = self._right_inner
        staged = (self._mode == self.STAGED)

        # ── simple text fields ───────────────────────────────────────────
        self._field_vars = {}
        for key, lbl in (
            ("dct:title",         "Title"),
            ("dcat:contactPoint", "Contact"),
            ("dcat:keyword",      "Keywords"),
            ("dct:issued",        "Issued"),
            ("dct:language",      "Language"),
        ):
            row = ttk.Frame(inner)
            row.pack(fill="x", padx=6, pady=2)
            ttk.Label(row, text=f"{lbl}:", width=10, anchor="e").pack(side="left")
            var = tk.StringVar(value=entry.get(key, ""))
            ttk.Entry(row, textvariable=var).pack(
                side="left", fill="x", expand=True)
            self._field_vars[key] = var

        # Error banner for failed entries
        if entry.get("_error"):
            ef = ttk.Frame(inner)
            ef.pack(fill="x", padx=6, pady=2)
            ttk.Label(ef, text=f"Extraction error: {entry['_error']}",
                      foreground="#cc0000",
                      wraplength=420).pack(anchor="w")

        ttk.Separator(inner, orient="horizontal").pack(fill="x", padx=6, pady=4)

        # ── authors ──────────────────────────────────────────────────────
        ah = ttk.Frame(inner)
        ah.pack(fill="x", padx=6)
        ttk.Label(ah, text="Authors",
                  font=("TkDefaultFont", 9, "bold")).pack(side="left")
        ttk.Button(ah, text="+ Add author", width=12,
                   command=self._add_author).pack(side="right")

        self._authors_frame = ttk.Frame(inner)
        self._authors_frame.pack(fill="x", padx=6, pady=2)

        self._entry_authors       = entry.setdefault("authors", [])
        self._entry_aff_decisions = entry.setdefault("_aff_decisions", [])
        self._rebuild_authors(staged)

        ttk.Separator(inner, orient="horizontal").pack(fill="x", padx=6, pady=4)

        # ── relations ────────────────────────────────────────────────────
        rh = ttk.Frame(inner)
        rh.pack(fill="x", padx=6)
        ttk.Label(rh, text="Relations (DOIs / citations)",
                  font=("TkDefaultFont", 9, "bold")).pack(side="left")
        ttk.Button(rh, text="+ Add", width=6,
                   command=self._add_relation).pack(side="right")

        self._relations_frame = ttk.Frame(inner)
        self._relations_frame.pack(fill="x", padx=6, pady=2)
        self._entry_relations = entry.setdefault("dct:relation", [])
        self._rebuild_relations()

        # ── action buttons ───────────────────────────────────────────────
        ab = self._action_bar
        if staged:
            ttk.Button(ab, text="Approve",
                       command=self._approve).pack(side="left", padx=4)
            ttk.Button(ab, text="Discard",
                       command=self._discard).pack(side="left", padx=4)
            ttk.Button(ab, text="Skip",
                       command=self._skip).pack(side="left", padx=4)
        else:
            ttk.Button(ab, text="Save",
                       command=self._save_approved).pack(side="left", padx=4)
            ttk.Button(ab, text="Delete",
                       command=self._delete_approved).pack(side="left", padx=4)

    # ── authors section ───────────────────────────────────────────────────────

    def _rebuild_authors(self, staged: bool | None = None):
        if staged is None:
            staged = (self._mode == self.STAGED)
        for w in self._author_widgets:
            w.destroy()
        self._author_widgets.clear()

        for i in range(len(self._entry_authors)):
            def make_remove(j=i):
                def _remove():
                    self._remove_author(j)
                return _remove

            aw = AuthorWidget(
                self._authors_frame,
                author=self._entry_authors[i],
                aff_decisions=self._entry_aff_decisions,
                registry=self._registry,
                staged=staged,
                on_remove=make_remove(i),
            )
            aw.pack(fill="x", pady=3)
            self._author_widgets.append(aw)

    def _remove_author(self, idx: int):
        if idx >= len(self._entry_authors):
            return
        name = self._entry_authors[idx].get("name", f"Author {idx+1}")
        if not messagebox.askyesno(
            "Remove author",
            f"Remove '{name}' and all their affiliations?", parent=self):
            return
        self._entry_aff_decisions[:] = [
            r for r in self._entry_aff_decisions
            if r.get("author") != name
        ]
        self._entry_authors.pop(idx)
        self._rebuild_authors()

    def _add_author(self):
        name = simpledialog.askstring(
            "Add author", "Author name:", parent=self)
        if name and name.strip():
            self._entry_authors.append(
                {"name": name.strip(), "affiliations": []})
            self._rebuild_authors()

    # ── relations section ─────────────────────────────────────────────────────

    def _rebuild_relations(self):
        for w in self._relations_frame.winfo_children():
            w.destroy()
        for i, rel in enumerate(self._entry_relations):
            row = ttk.Frame(self._relations_frame)
            row.pack(fill="x", pady=1)
            var = tk.StringVar(value=rel)

            def make_updater(j=i, v=var):
                def _update(*_):
                    if j < len(self._entry_relations):
                        self._entry_relations[j] = v.get()
                return _update

            var.trace_add("write", make_updater(i, var))
            ttk.Entry(row, textvariable=var).pack(
                side="left", fill="x", expand=True)

            def make_remover(j=i):
                def _remove():
                    if j < len(self._entry_relations):
                        self._entry_relations.pop(j)
                    self._rebuild_relations()
                return _remove

            ttk.Button(row, text="x", width=2,
                       command=make_remover(i)).pack(side="right")

    def _add_relation(self):
        val = simpledialog.askstring(
            "Add relation", "DOI or citation string:", parent=self)
        if val and val.strip():
            self._entry_relations.append(val.strip())
            self._rebuild_relations()

    # ── field collection ──────────────────────────────────────────────────────

    def _collect_edits(self, entry: dict):
        """Write simple text field vars back into the entry dict."""
        for key, var in self._field_vars.items():
            entry[key] = var.get()

    # ── staged actions ────────────────────────────────────────────────────────

    def _approve(self):
        if not self._current:
            return
        entry = self._current
        self._collect_edits(entry)

        # Warn about unresolved pending decisions
        pending = [r for r in entry.get("_aff_decisions", [])
                   if r.get("decision") == "pending"]
        if pending:
            sample = ", ".join(
                f"{r['author']}/{r['raw'][:25]}" for r in pending[:3])
            if not messagebox.askyesno(
                "Pending affiliation decisions",
                f"{len(pending)} affiliation(s) still unresolved:\n{sample}\n\n"
                "Approve anyway? (raw strings will be kept as-is)", parent=self):
                return

        # Apply decisions → replace raw affiliations with canonicals
        final = shared.apply_aff_decisions(entry)

        # Update registry
        registry = shared.load_registry()
        for dec in entry.get("_aff_decisions", []):
            decision = dec.get("decision", "")
            raw      = dec.get("raw", "")
            if not raw:
                continue
            if decision in ("existing", "auto_existing"):
                canon = dec.get("matched_canonical") or raw
                if canon and raw != canon:
                    shared.registry_add_variant(registry, canon, raw)
            elif decision in ("new", "auto_new"):
                canon = dec.get("new_canonical") or raw
                if canon:
                    shared.registry_add_canonical(registry, canon, raw)
        shared.save_registry(registry)
        self._registry = registry

        # Append to abstract_metadata.json
        approved = shared.load_json(shared.METADATA_PATH)
        approved.append(final)
        shared.save_json(approved, shared.METADATA_PATH)

        # Remove from staging.json
        ft = entry.get("file_title", "")
        staging = shared.load_json(shared.STAGING_PATH)
        staging = [e for e in staging if e.get("file_title") != ft]
        shared.save_json(staging, shared.STAGING_PATH)

        self._status_var.set(f"Approved: {ft}")
        self._current = None
        self._clear_detail()
        self._populate_list()

    def _discard(self):
        if not self._current:
            return
        ft = self._current.get("file_title", "this entry")
        if not messagebox.askyesno(
            "Discard entry",
            f"Permanently discard '{ft}' from staging.json?\n"
            "This cannot be undone.", parent=self):
            return
        staging = shared.load_json(shared.STAGING_PATH)
        staging = [e for e in staging if e.get("file_title") != ft]
        shared.save_json(staging, shared.STAGING_PATH)
        self._current = None
        self._clear_detail()
        self._populate_list()

    def _skip(self):
        """Advance to the next entry without modifying anything."""
        if not self._filtered:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        cur = sel[0]
        nxt = (cur + 1) % len(self._filtered)
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(nxt)
        self._listbox.see(nxt)
        self._on_select()

    # ── approved actions ──────────────────────────────────────────────────────

    def _save_approved(self):
        if not self._current:
            return
        self._collect_edits(self._current)
        ft = self._current.get("file_title", "")
        approved = shared.load_json(shared.METADATA_PATH)
        for i, e in enumerate(approved):
            if e.get("file_title") == ft:
                approved[i] = self._current
                break
        else:
            approved.append(self._current)
        shared.save_json(approved, shared.METADATA_PATH)
        self._status_var.set(f"Saved: {ft}")

    def _delete_approved(self):
        if not self._current:
            return
        ft    = self._current.get("file_title", "this entry")
        title = self._current.get("dct:title", ft)
        if not messagebox.askyesno(
            "Delete entry",
            f"Delete '{title[:70]}'\nfrom abstract_metadata.json?\n"
            "This cannot be undone.", parent=self):
            return
        approved = shared.load_json(shared.METADATA_PATH)
        approved = [e for e in approved if e.get("file_title") != ft]
        shared.save_json(approved, shared.METADATA_PATH)
        self._current = None
        self._clear_detail()
        self._populate_list()
        self._status_var.set(f"Deleted: {ft}")

    def destroy(self):
        self._close_pdf()
        super().destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
