"""
Abstract Deletion Tool
Searches the TTL dataset and deletes selected abstracts together with their
orphaned person/organization nodes, the matching JSON entry, and the source PDF.
"""

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from difflib import SequenceMatcher

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

# ── Paths (relative to repo root) ──────────────────────────────────────────
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_TTL  = os.path.join(REPO_ROOT, "data", "rdf",
                            "abstracts_katalytikertagung_w_affili_w_classes.ttl")
DEFAULT_JSON = os.path.join(REPO_ROOT, "data", "intermediate",
                            "metadata_output_20251023_1016_cleaned_affiliations3.json")
PDF_DIR      = os.path.join(REPO_ROOT, "data", "abstracts")

# ── Namespaces ──────────────────────────────────────────────────────────────
EX     = Namespace("http://example.org/katalytikertagung/")
DCT    = Namespace("http://purl.org/dc/terms/")
SCHEMA = Namespace("https://schema.org/")
DCAT1  = Namespace("https://www.w3.org/ns/dcat#")
FOAF   = Namespace("http://xmlns.com/foaf/0.1/")


# ── RDF helpers ─────────────────────────────────────────────────────────────

def strip_cr(path):
    """Remove Windows \\r characters that rdflib may introduce on serialization."""
    with open(path, "rb") as f:
        data = f.read()
    cleaned = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if cleaned != data:
        with open(path, "wb") as f:
            f.write(cleaned)


def load_graph(path):
    g = Graph()
    g.parse(path, format="turtle")
    return g


def all_abstract_uris(g):
    """Return all abstract URIs (rdfs:subClassOf ex:Abstract)."""
    return list(g.subjects(RDFS.subClassOf, EX.Abstract))


def abstract_title(g, uri):
    t = g.value(uri, DCT.title)
    return str(t) if t else str(g.value(uri, RDFS.label, default=""))


def abstract_contributors(g, uri):
    """Return list of (person_uri, label) for dct:contributor."""
    result = []
    for p in g.objects(uri, DCT.contributor):
        label = g.value(p, RDFS.label)
        result.append((p, str(label) if label else str(p)))
    return result


def abstract_contact(g, uri):
    c = g.value(uri, DCAT1.contactPoint)
    if c:
        label = g.value(c, RDFS.label)
        return str(label) if label else str(c)
    return ""


def abstract_organizations(g, uri):
    """Return list of (org_uri, label) via schema:Organization property on abstract."""
    result = []
    for o in g.objects(uri, SCHEMA.Organization):
        label = g.value(o, RDFS.label)
        result.append((o, str(label) if label else str(o)))
    return result


def abstract_date(g, uri):
    d = g.value(uri, DCT.issued)
    return str(d) if d else ""


# ── Search ───────────────────────────────────────────────────────────────────

def _score(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def search_abstracts(g, query, mode):
    """
    mode: 'title' | 'author' | 'affiliation'
    Returns list of (uri, display_title, score) sorted by score desc.
    """
    q = query.lower().strip()
    if not q:
        return []

    results = []
    for uri in all_abstract_uris(g):
        score = 0.0

        if mode == "title":
            text = abstract_title(g, uri).lower()
            score = max(_score(q, text), float(q in text))

        elif mode == "author":
            for _, name in abstract_contributors(g, uri):
                s = max(_score(q, name.lower()), float(q in name.lower()))
                score = max(score, s)

        elif mode == "affiliation":
            for _, label in abstract_organizations(g, uri):
                s = max(_score(q, label.lower()), float(q in label.lower()))
                score = max(score, s)

        if score >= 0.3:
            results.append((uri, abstract_title(g, uri), score))

    results.sort(key=lambda x: x[2], reverse=True)
    return results[:30]


# ── Deletion logic ───────────────────────────────────────────────────────────

def _is_orphaned_person(g, person_uri, excluding_abstract):
    """True if no abstract other than excluding_abstract references this person."""
    for abstract in g.subjects(DCT.contributor, person_uri):
        if abstract != excluding_abstract:
            return False
    for abstract in g.subjects(DCAT1.contactPoint, person_uri):
        if abstract != excluding_abstract:
            return False
    return True


def _is_orphaned_org(g, org_uri, excluding_abstract):
    """True if no abstract other than excluding_abstract references this org."""
    for abstract in g.subjects(SCHEMA.Organization, org_uri):
        if abstract != excluding_abstract:
            return False
    return True


def preview_deletion(g, uri):
    """
    Return a dict describing everything that will be removed:
      title, orphaned_persons [(uri, label)], orphaned_orgs [(uri, label)],
      pdf_filename (or None)
    """
    title = abstract_title(g, uri)

    orphaned_persons = []
    for p_uri, p_label in abstract_contributors(g, uri):
        if _is_orphaned_person(g, p_uri, uri):
            orphaned_persons.append((p_uri, p_label))
    # Also check contact point
    c = g.value(uri, DCAT1.contactPoint)
    if c and _is_orphaned_person(g, c, uri):
        c_label = str(g.value(c, RDFS.label, default=str(c)))
        if (c, c_label) not in orphaned_persons:
            orphaned_persons.append((c, c_label))

    orphaned_orgs = []
    for o_uri, o_label in abstract_organizations(g, uri):
        if _is_orphaned_org(g, o_uri, uri):
            orphaned_orgs.append((o_uri, o_label))

    return {
        "title": title,
        "orphaned_persons": orphaned_persons,
        "orphaned_orgs": orphaned_orgs,
    }


def delete_abstract(g, json_data, uri):
    """
    Remove the abstract (and orphaned nodes) from the graph,
    remove from json_data list, delete the PDF.
    Returns (pdf_deleted: bool, pdf_path: str|None, warnings: [str])
    """
    warnings = []
    preview = preview_deletion(g, uri)
    title = preview["title"]

    # ── Remove triples of orphaned persons ──
    for p_uri, _ in preview["orphaned_persons"]:
        for s, p, o in list(g.triples((p_uri, None, None))):
            g.remove((s, p, o))
        for s, p, o in list(g.triples((None, None, p_uri))):
            g.remove((s, p, o))

    # ── Remove triples of orphaned orgs ──
    for o_uri, _ in preview["orphaned_orgs"]:
        for s, p, o in list(g.triples((o_uri, None, None))):
            g.remove((s, p, o))
        for s, p, o in list(g.triples((None, None, o_uri))):
            g.remove((s, p, o))

    # ── Remove the abstract node itself ──
    for s, p, o in list(g.triples((uri, None, None))):
        g.remove((s, p, o))
    for s, p, o in list(g.triples((None, None, uri))):
        g.remove((s, p, o))

    # ── Remove from JSON data (match by title) ──
    json_idx = next(
        (i for i, e in enumerate(json_data) if e.get("dct:title", "") == title),
        None
    )
    pdf_path = None
    if json_idx is not None:
        file_title = json_data[json_idx].get("file_title", "")
        json_data.pop(json_idx)
        if file_title:
            pdf_path = os.path.join(PDF_DIR, file_title + ".pdf")
    else:
        warnings.append(f"No matching JSON entry found for title:\n  {title[:80]}")

    # ── Delete PDF ──
    pdf_deleted = False
    if pdf_path and os.path.isfile(pdf_path):
        os.remove(pdf_path)
        pdf_deleted = True
    elif pdf_path:
        warnings.append(f"PDF not found: {os.path.basename(pdf_path)}")

    return pdf_deleted, pdf_path, warnings


# ── GUI ──────────────────────────────────────────────────────────────────────

class DeletionTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Abstract Deletion Tool")
        self.root.geometry("900x680")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.graph = None
        self.json_data = None
        self.ttl_path = None
        self.json_path = None
        self.search_results = []   # list of (uri, title, score)

        self._build_ui()
        self._auto_load()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=8)
        outer.grid(sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        # ── File section ──
        file_frame = ttk.LabelFrame(outer, text="Dataset files", padding=6)
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="TTL:").grid(row=0, column=0, sticky="w")
        self.ttl_label = ttk.Label(file_frame, text="—", anchor="w", relief="sunken")
        self.ttl_label.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(file_frame, text="Browse…", command=self._browse_ttl).grid(row=0, column=2)

        ttk.Label(file_frame, text="JSON:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.json_label = ttk.Label(file_frame, text="—", anchor="w", relief="sunken")
        self.json_label.grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 0))
        ttk.Button(file_frame, text="Browse…", command=self._browse_json).grid(row=1, column=2, pady=(4, 0))

        # ── Search section ──
        search_frame = ttk.LabelFrame(outer, text="Search", padding=6)
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        search_frame.columnconfigure(1, weight=1)

        self.search_mode = tk.StringVar(value="title")
        for col, (val, txt) in enumerate([("title", "Title"), ("author", "Author"), ("affiliation", "Affiliation")]):
            ttk.Radiobutton(search_frame, text=txt, variable=self.search_mode,
                            value=val).grid(row=0, column=col, padx=6, sticky="w")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        entry = ttk.Entry(search_frame, textvariable=self.search_var, width=55)
        entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        entry.bind("<Return>", lambda _: self._on_search())

        # ── Browse-PDF row ──
        sep = ttk.Separator(search_frame, orient="horizontal")
        sep.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 4))

        ttk.Label(search_frame, text="Or select directly:").grid(row=3, column=0, sticky="w", padx=6)
        ttk.Button(search_frame, text="Browse PDF…",
                   command=self._browse_pdf).grid(row=3, column=1, sticky="w", padx=4)
        self.pdf_browse_label = ttk.Label(search_frame, text="", anchor="w",
                                          foreground="gray", font=("TkDefaultFont", 9))
        self.pdf_browse_label.grid(row=3, column=2, sticky="ew", padx=4)

        # ── Results + detail pane ──
        pane = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        pane.grid(row=2, column=0, sticky="nsew")

        # Left: results list
        left = ttk.LabelFrame(pane, text="Results", padding=4)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.results_box = tk.Listbox(left, selectmode=tk.SINGLE, activestyle="dotbox",
                                      font=("TkDefaultFont", 10))
        sb = ttk.Scrollbar(left, command=self.results_box.yview)
        self.results_box.config(yscrollcommand=sb.set)
        self.results_box.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.results_box.bind("<<ListboxSelect>>", self._on_select)
        pane.add(left, weight=2)

        # Right: detail panel
        right = ttk.LabelFrame(pane, text="Abstract details", padding=4)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.detail_text = tk.Text(right, wrap="word", state="disabled",
                                   font=("TkDefaultFont", 10), relief="flat",
                                   background=self.root.cget("background"))
        ds = ttk.Scrollbar(right, command=self.detail_text.yview)
        self.detail_text.config(yscrollcommand=ds.set)
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        ds.grid(row=0, column=1, sticky="ns")
        pane.add(right, weight=3)

        # ── Bottom bar ──
        bottom = ttk.Frame(outer, padding=(0, 6, 0, 0))
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.status = ttk.Label(bottom, text="Load a dataset to begin.", anchor="w", relief="sunken")
        self.status.grid(row=0, column=0, sticky="ew")

        self.delete_btn = ttk.Button(bottom, text="Delete selected abstract",
                                     command=self._confirm_delete, state="disabled")
        self.delete_btn.grid(row=0, column=1, padx=(8, 0))

    # ── File loading ─────────────────────────────────────────────────────────

    def _auto_load(self):
        if os.path.isfile(DEFAULT_TTL) and os.path.isfile(DEFAULT_JSON):
            self._load(DEFAULT_TTL, DEFAULT_JSON)

    def _browse_ttl(self):
        p = filedialog.askopenfilename(title="Select TTL file",
                                       filetypes=[("Turtle", "*.ttl"), ("All", "*.*")])
        if p:
            self._load(p, self.json_path or DEFAULT_JSON)

    def _browse_json(self):
        p = filedialog.askopenfilename(title="Select JSON file",
                                       filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if p:
            self._load(self.ttl_path or DEFAULT_TTL, p)

    def _browse_pdf(self):
        """Let the user pick a PDF; look it up in JSON + TTL and show its details."""
        if not self.graph or not self.json_data:
            messagebox.showinfo("No dataset", "Please load the dataset first.")
            return

        pdf_path = filedialog.askopenfilename(
            title="Select abstract PDF",
            initialdir=PDF_DIR,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not pdf_path:
            return

        file_title = os.path.splitext(os.path.basename(pdf_path))[0]
        self.pdf_browse_label.config(text=file_title + ".pdf")

        # ── Find matching JSON entry by file_title ──
        json_entry = next(
            (e for e in self.json_data if e.get("file_title", "") == file_title),
            None
        )
        if json_entry is None:
            messagebox.showerror(
                "Not found",
                f"No JSON entry found for:\n  {file_title}.pdf\n\n"
                "The file may not be in the dataset."
            )
            self.pdf_browse_label.config(text=file_title + ".pdf  ✗ not in dataset",
                                         foreground="red")
            return

        title = json_entry.get("dct:title", "")

        # ── Find matching TTL abstract by title ──
        uri = next(
            (u for u in all_abstract_uris(self.graph)
             if abstract_title(self.graph, u) == title),
            None
        )
        if uri is None:
            messagebox.showerror(
                "Not found",
                f"JSON entry found but no matching TTL abstract for title:\n  {title[:80]}"
            )
            self.pdf_browse_label.config(text=file_title + ".pdf  ✗ not in TTL",
                                         foreground="red")
            return

        # ── Populate results list with just this abstract, then select it ──
        self.search_results = [(uri, title, 1.0)]
        self.results_box.delete(0, tk.END)
        short = title[:80] + ("…" if len(title) > 80 else "")
        self.results_box.insert(tk.END, short)
        self.results_box.selection_set(0)
        self.results_box.activate(0)

        self._show_detail(uri)
        self.delete_btn.config(state="normal")
        self.pdf_browse_label.config(text=file_title + ".pdf  ✓ found", foreground="green")
        self._set_status(f"PDF resolved: {file_title}.pdf")

    def _load(self, ttl_path, json_path):
        try:
            self._set_status("Loading…")
            self.root.update_idletasks()
            self.graph = load_graph(ttl_path)
            with open(json_path, encoding="utf-8") as f:
                self.json_data = json.load(f)
            self.ttl_path  = ttl_path
            self.json_path = json_path
            self.ttl_label.config(text=os.path.basename(ttl_path))
            self.json_label.config(text=os.path.basename(json_path))
            n = len(all_abstract_uris(self.graph))
            self._set_status(f"Loaded {n} abstracts.  Type to search.")
        except Exception as e:
            messagebox.showerror("Load error", str(e))
            self._set_status("Load failed.")

    # ── Search ───────────────────────────────────────────────────────────────

    def _on_search(self):
        if not self.graph:
            return
        q = self.search_var.get().strip()
        if len(q) < 2:
            self.results_box.delete(0, tk.END)
            self.search_results = []
            self._clear_detail()
            return

        self.search_results = search_abstracts(self.graph, q, self.search_mode.get())
        self.results_box.delete(0, tk.END)
        for _, title, _ in self.search_results:
            short = title[:80] + ("…" if len(title) > 80 else "")
            self.results_box.insert(tk.END, short)

        n = len(self.search_results)
        self._set_status(f"{n} result{'s' if n != 1 else ''} found.")
        self._clear_detail()
        self.delete_btn.config(state="disabled")

    # ── Selection ────────────────────────────────────────────────────────────

    def _on_select(self, _event=None):
        sel = self.results_box.curselection()
        if not sel or not self.graph:
            self._clear_detail()
            self.delete_btn.config(state="disabled")
            return

        uri, title, _ = self.search_results[sel[0]]
        self._show_detail(uri)
        self.delete_btn.config(state="normal")

    def _show_detail(self, uri):
        g = self.graph
        title     = abstract_title(g, uri)
        date      = abstract_date(g, uri)
        authors   = abstract_contributors(g, uri)
        contact   = abstract_contact(g, uri)
        orgs      = abstract_organizations(g, uri)

        # Find PDF filename via JSON
        pdf_name = "—"
        for entry in (self.json_data or []):
            if entry.get("dct:title", "") == title:
                ft = entry.get("file_title", "")
                pdf_name = ft + ".pdf" if ft else "—"
                break

        lines = []
        lines.append(f"Title:\n  {title}\n")
        lines.append(f"Date:  {date}\n")
        lines.append(f"PDF:   {pdf_name}\n")
        lines.append(f"\nAuthors ({len(authors)}):")
        for _, name in authors:
            lines.append(f"  • {name}")
        if contact:
            lines.append(f"\nContact point:  {contact}")
        lines.append(f"\nAffiliations ({len(orgs)}):")
        for _, label in orgs:
            lines.append(f"  • {label}")

        # Orphan preview
        preview = preview_deletion(g, uri)
        if preview["orphaned_persons"] or preview["orphaned_orgs"]:
            lines.append("\n── Will also be removed (no other abstract references them) ──")
            for _, name in preview["orphaned_persons"]:
                lines.append(f"  person: {name}")
            for _, label in preview["orphaned_orgs"]:
                lines.append(f"  org:    {label}")

        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.config(state="disabled")

    def _clear_detail(self):
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.config(state="disabled")

    # ── Deletion ─────────────────────────────────────────────────────────────

    def _confirm_delete(self):
        sel = self.results_box.curselection()
        if not sel:
            return

        uri, title, _ = self.search_results[sel[0]]
        preview = preview_deletion(self.graph, uri)

        msg_lines = [f"Delete this abstract?\n\n{title[:100]}\n"]
        if preview["orphaned_persons"]:
            msg_lines.append("\nOrphaned persons to remove:")
            for _, n in preview["orphaned_persons"]:
                msg_lines.append(f"  • {n}")
        if preview["orphaned_orgs"]:
            msg_lines.append("\nOrphaned organizations to remove:")
            for _, n in preview["orphaned_orgs"]:
                msg_lines.append(f"  • {n}")
        msg_lines.append("\nThe PDF file will also be deleted.\nThis cannot be undone.")

        if not messagebox.askyesno("Confirm deletion", "\n".join(msg_lines), icon="warning"):
            return

        # Execute
        pdf_deleted, pdf_path, warnings = delete_abstract(self.graph, self.json_data, uri)

        # Save TTL
        try:
            self.graph.serialize(destination=self.ttl_path, format="turtle")
            strip_cr(self.ttl_path)
        except Exception as e:
            messagebox.showerror("Save error", f"Could not save TTL:\n{e}")
            return

        # Save JSON
        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(self.json_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Save error", f"Could not save JSON:\n{e}")
            return

        # Remove from results list and clear detail
        self.search_results.pop(sel[0])
        self.results_box.delete(sel[0])
        self._clear_detail()
        self.delete_btn.config(state="disabled")

        n_remaining = len(all_abstract_uris(self.graph))
        pdf_msg = f", PDF deleted" if pdf_deleted else ""
        self._set_status(f"Deleted. {n_remaining} abstracts remaining{pdf_msg}.")

        if warnings:
            messagebox.showwarning("Warnings", "\n".join(warnings))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _set_status(self, msg):
        self.status.config(text=msg)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = DeletionTool(root)
    root.mainloop()
