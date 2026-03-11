import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import glob
import json
from datetime import datetime
from langdetect import detect
import re
import pandas as pd
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTTextLine
from crossref.restful import Works as Crossref
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image, ImageTk

cr = Crossref()


class MetadataExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Metadata Extractor")
        self.root.geometry("1600x900")

        self.pdf_files = []
        self.current_index = 0
        self.records = []

        self.create_widgets()
        self.internal_records = {}
        self.user_modified = set()

    def create_widgets(self):
        # Top frame for file selection
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Button(top_frame, text="Select JSON File", command=self.select_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Select PDF Folder", command=self.select_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Start Workflow", command=self.start_workflow).pack(side=tk.LEFT, padx=5)

        self.folder_label = ttk.Label(top_frame, text="No folder selected")
        self.folder_label.pack(side=tk.LEFT, padx=5)

        self.json_label = ttk.Label(top_frame, text="No JSON loaded")
        self.json_label.pack(side=tk.LEFT, padx=5)

        self.json_path = None
        self.loaded_json_data = []

        # Main content frame - 3 columns
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Column 1: Metadata Fields (1/3 of width)
        left_frame = ttk.LabelFrame(main_frame, text="Metadata Fields")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        canvas = tk.Canvas(left_frame, bg='white')
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.metadata_fields = {}
        self.author_widgets = []
        self.relation_entries = []

        # Simple metadata fields
        simple_metadata_keys = [
            'dct:title',
            'dcat:contactPoint',
            'dcat:keyword',
            'dct:language',
        ]

        for key in simple_metadata_keys:
            frame = ttk.Frame(self.scrollable_frame)
            frame.pack(fill=tk.X, padx=5, pady=5)
            frame.grid_columnconfigure(0, weight=1)  # Make column expandable

            label = ttk.Label(frame, text=key, font=("Arial", 9, "bold"))
            label.grid(row=0, column=0, sticky="w")

            # Use single-line Entry for contactPoint, keyword, and language
            if key in ['dcat:contactPoint', 'dcat:keyword', 'dct:language']:
                entry = ttk.Entry(frame, font=("Arial", 9))
                entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
                # Store as dict with 'entry' key for consistency
                self.metadata_fields[key] = {'widget': entry, 'type': 'entry'}
            else:
                # Use Text widget for title
                entry = tk.Text(frame, height=5, wrap=tk.WORD, font=("Arial", 8))
                entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
                self.metadata_fields[key] = {'widget': entry, 'type': 'text'}

        # Relations section with add button
        self.relations_container_frame = ttk.Frame(self.scrollable_frame)
        self.relations_container_frame.pack(fill=tk.X, padx=5, pady=5)

        relations_header = ttk.Frame(self.relations_container_frame)
        relations_header.pack(fill=tk.X)

        ttk.Label(relations_header, text="dct:relation", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(relations_header, text="+ Add Relation", command=self.add_relation_field).pack(side=tk.RIGHT, padx=5)

        self.relations_fields_frame = ttk.Frame(self.relations_container_frame)
        self.relations_fields_frame.pack(fill=tk.X, pady=5)

        # Authors section with add button
        self.authors_container_frame = ttk.Frame(self.scrollable_frame)
        self.authors_container_frame.pack(fill=tk.X, padx=5, pady=5)

        authors_header = ttk.Frame(self.authors_container_frame)
        authors_header.pack(fill=tk.X)

        ttk.Label(authors_header, text="Authors", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(authors_header, text="+ Add Author", command=self.add_author_field).pack(side=tk.RIGHT, padx=5)

        self.authors_fields_frame = ttk.Frame(self.authors_container_frame)
        self.authors_fields_frame.pack(fill=tk.X, pady=5)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Column 2: PDF Preview (1/3 of width)
        pdf_frame = ttk.LabelFrame(main_frame, text="PDF Preview")
        pdf_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        pdf_control_frame = ttk.Frame(pdf_frame)
        pdf_control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Button(pdf_control_frame, text="Zoom In (+)", command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        ttk.Button(pdf_control_frame, text="Zoom Out (-)", command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(pdf_control_frame, text="Fit", command=self.fit_to_window).pack(side=tk.LEFT, padx=2)

        self.page_label = ttk.Label(pdf_control_frame, text="Page 1/1")
        self.page_label.pack(side=tk.LEFT, padx=10)

        pdf_container = ttk.Frame(pdf_frame)
        pdf_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.pdf_canvas = tk.Canvas(pdf_container, bg='gray')
        h_scrollbar = ttk.Scrollbar(pdf_container, orient=tk.HORIZONTAL, command=self.pdf_canvas.xview)
        v_scrollbar = ttk.Scrollbar(pdf_container, orient=tk.VERTICAL, command=self.pdf_canvas.yview)

        self.pdf_canvas.config(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

        self.pdf_canvas.grid(row=0, column=0, sticky="nsew")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")

        pdf_container.grid_rowconfigure(0, weight=1)
        pdf_container.grid_columnconfigure(0, weight=1)

        self.pdf_canvas.bind("<Button-1>", self.on_canvas_press)
        self.pdf_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.pdf_canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.pdf_canvas.bind("<Button-4>", self.on_mousewheel)
        self.pdf_canvas.bind("<Button-5>", self.on_mousewheel)

        # Column 3: Extracted Text (1/3 of width)
        text_frame = ttk.LabelFrame(main_frame, text="Extracted Text")
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        text_label = ttk.Label(text_frame, text="Copy text to metadata fields:", font=("Arial", 9, "bold"))
        text_label.pack(anchor=tk.W, padx=5, pady=5)

        self.extracted_text_widget = tk.Text(text_frame, wrap=tk.WORD, bg='white', font=("Arial", 8))
        text_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.extracted_text_widget.yview)
        self.extracted_text_widget.config(yscrollcommand=text_scrollbar.set)

        self.extracted_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Initialize PDF display variables
        self.dpi = 150
        self.current_pdf_path = None
        self.pdf_photo_image = None
        self.canvas_x = 0
        self.canvas_y = 0

        # Bottom frame - Navigation
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        ttk.Button(bottom_frame, text="◀ Previous", command=self.prev_file).pack(side=tk.LEFT, padx=2)

        self.file_label = ttk.Label(bottom_frame, text="No files loaded")
        self.file_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(bottom_frame, text="Next ▶", command=self.next_file).pack(side=tk.LEFT, padx=2)

        ttk.Label(bottom_frame, text="Go to PDF #:").pack(side=tk.LEFT, padx=(20, 2))
        self.goto_entry = ttk.Entry(bottom_frame, width=5)
        self.goto_entry.pack(side=tk.LEFT)
        ttk.Button(bottom_frame, text="Go", command=self.go_to_pdf).pack(side=tk.LEFT, padx=2)

        ttk.Button(bottom_frame, text="Finish & Save", command=self.finish_and_save).pack(side=tk.RIGHT, padx=10)

    def add_relation_field(self, relation_text=""):
        """Add a single relation entry field"""
        relation_frame = ttk.Frame(self.relations_fields_frame)
        relation_frame.pack(fill=tk.X, pady=2)

        # Relation entry
        relation_entry = ttk.Entry(relation_frame, font=("Arial", 8))
        relation_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 5))
        relation_entry.insert(0, relation_text)

        # Remove relation button
        remove_btn = ttk.Button(relation_frame, text="×", width=3,
                                command=lambda: self.remove_relation_field(relation_frame, relation_entry))
        remove_btn.pack(side=tk.RIGHT)

        # Store reference
        self.relation_entries.append({
            'frame': relation_frame,
            'entry': relation_entry
        })

    def remove_relation_field(self, relation_frame, relation_entry):
        """Remove a single relation entry"""
        # Remove from list
        self.relation_entries = [
            rel for rel in self.relation_entries
            if rel['entry'] != relation_entry
        ]
        # Destroy frame
        relation_frame.destroy()

        # Ensure at least one relation field remains
        if not self.relation_entries:
            self.add_relation_field("")

    def clear_relation_fields(self):
        """Clear all relation fields"""
        for rel_widget in self.relation_entries:
            rel_widget['frame'].destroy()
        self.relation_entries = []

    def add_author_field(self, name="", affiliations=None):
        """Add a new author field with name and affiliations"""
        if affiliations is None:
            affiliations = [""]

        author_frame = ttk.Frame(self.authors_fields_frame, relief=tk.RIDGE, borderwidth=2)
        author_frame.pack(fill=tk.X, pady=5)

        # Author header with remove button
        header_frame = ttk.Frame(author_frame)
        header_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(header_frame, text=f"Author {len(self.author_widgets) + 1}", font=("Arial", 9, "bold")).pack(
            side=tk.LEFT)
        remove_btn = ttk.Button(header_frame, text="Remove", command=lambda: self.remove_author_field(author_frame))
        remove_btn.pack(side=tk.RIGHT)

        # Author name
        name_frame = ttk.Frame(author_frame)
        name_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(name_frame, text="Name:", width=12).pack(side=tk.LEFT)
        name_entry = ttk.Entry(name_frame, font=("Arial", 9))
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        name_entry.insert(0, name)

        # Affiliations header with add button
        affiliations_header_frame = ttk.Frame(author_frame)
        affiliations_header_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(affiliations_header_frame, text="Affiliations:", width=12).pack(side=tk.LEFT)
        add_affiliation_btn = ttk.Button(affiliations_header_frame, text="+ Add Affiliation",
                                         command=lambda: self.add_affiliation_to_author(author_widget))
        add_affiliation_btn.pack(side=tk.RIGHT)

        # Affiliations container
        affiliations_container = ttk.Frame(author_frame)
        affiliations_container.pack(fill=tk.X, padx=5, pady=2)

        # Store reference to this author widget
        author_widget = {
            'frame': author_frame,
            'name': name_entry,
            'affiliations_container': affiliations_container,
            'affiliation_entries': []
        }
        self.author_widgets.append(author_widget)

        # Add affiliation fields
        if not affiliations or affiliations == [""]:
            self.add_affiliation_to_author(author_widget, "")
        else:
            for affiliation in affiliations:
                self.add_affiliation_to_author(author_widget, affiliation)

    def add_affiliation_to_author(self, author_widget, affiliation_text=""):
        """Add a single affiliation entry field to an author"""
        affiliation_frame = ttk.Frame(author_widget['affiliations_container'])
        affiliation_frame.pack(fill=tk.X, pady=2)

        # Affiliation entry
        affiliation_entry = ttk.Entry(affiliation_frame, font=("Arial", 8))
        affiliation_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 5))
        affiliation_entry.insert(0, affiliation_text)

        # Remove affiliation button
        remove_btn = ttk.Button(affiliation_frame, text="×", width=3,
                                command=lambda: self.remove_affiliation_from_author(author_widget, affiliation_frame,
                                                                                    affiliation_entry))
        remove_btn.pack(side=tk.RIGHT)

        # Store reference
        author_widget['affiliation_entries'].append({
            'frame': affiliation_frame,
            'entry': affiliation_entry
        })

    def remove_affiliation_from_author(self, author_widget, affiliation_frame, affiliation_entry):
        """Remove a single affiliation entry from an author"""
        # Remove from list
        author_widget['affiliation_entries'] = [
            aff for aff in author_widget['affiliation_entries']
            if aff['entry'] != affiliation_entry
        ]
        # Destroy frame
        affiliation_frame.destroy()

        # Ensure at least one affiliation field remains
        if not author_widget['affiliation_entries']:
            self.add_affiliation_to_author(author_widget, "")

    def remove_author_field(self, author_frame):
        """Remove an author field"""
        # Find and remove from author_widgets list
        self.author_widgets = [w for w in self.author_widgets if w['frame'] != author_frame]
        author_frame.destroy()

        # Update author numbers
        for idx, widget in enumerate(self.author_widgets):
            # Find the label in the header frame
            for child in widget['frame'].winfo_children():
                if isinstance(child, ttk.Frame):
                    for label in child.winfo_children():
                        if isinstance(label, ttk.Label) and label.cget("text").startswith("Author"):
                            label.config(text=f"Author {idx + 1}")
                            break
                    break

    def clear_author_fields(self):
        """Clear all author fields"""
        for widget in self.author_widgets:
            widget['frame'].destroy()
        self.author_widgets = []

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select folder with PDF files")
        if not folder:
            return

        self.pdf_files = sorted(glob.glob(os.path.join(folder, "**", "*.pdf"), recursive=True))
        if not self.pdf_files:
            messagebox.showwarning("No Files", "No PDF files found in selected folder.")
            return

        for f in self.pdf_files:
            basename = os.path.splitext(os.path.basename(f))[0]
            if basename not in self.internal_records:
                self.internal_records[basename] = {"file_title": basename}

        self.folder_label.config(text=f"{len(self.pdf_files)} PDFs ready. Press 'Start Workflow' to begin.")
        self.file_label.config(text="Folder loaded.")

    def select_json(self):
        file_path = filedialog.askopenfilename(
            title="Select JSON File",
            filetypes=[("JSON files", "*.json")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.loaded_json_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load JSON file: {str(e)}")
            return

        self.internal_records.clear()
        for record in self.loaded_json_data:
            if "file_title" in record:
                title = str(record["file_title"]).strip()
                self.internal_records[title] = record

        self.user_modified.clear()
        self.json_label.config(text=f"Loaded {len(self.internal_records)} entries")
        messagebox.showinfo("JSON Loaded", f"Loaded {len(self.internal_records)} existing entries.")

    def start_workflow(self):
        if not hasattr(self, 'pdf_files') or not self.pdf_files:
            messagebox.showwarning("No PDFs", "Please select a PDF folder first.")
            return

        start_index = 0

        if self.loaded_json_data:
            existing_titles = set(record.get("file_title", "").strip() for record in self.loaded_json_data)

            for i, f in enumerate(self.pdf_files):
                basename = os.path.splitext(os.path.basename(f))[0]
                if basename not in existing_titles:
                    start_index = i
                    break
            else:
                messagebox.showinfo("Info", "All PDFs in folder are already in the JSON file.")
                start_index = 0

            messagebox.showinfo("Workflow Setup", f"Starting at PDF #{start_index + 1}")
        else:
            messagebox.showinfo("Workflow Setup", "No JSON loaded. Starting from first file.")

        self.current_index = start_index
        self.records = []
        self.load_current_file()

    def load_current_file(self):
        if not self.pdf_files:
            return

        pdf_path = self.pdf_files[self.current_index]
        name = os.path.splitext(os.path.basename(pdf_path))[0]

        existing_record = self.internal_records.get(name, {})

        if 'file_title' not in existing_record:
            existing_record['file_title'] = name

        text = self.extract_text_simple(pdf_path)
        recommendation_data = self.extract_metadata_from_text(text, pdf_path, fallback_title=name)

        final_metadata = existing_record.copy()

        for key, rec_value in recommendation_data.items():
            if key in ['authors', 'dct:relation']:
                # Skip authors and relations in this loop, handle separately
                continue

            current_value = final_metadata.get(key)

            is_empty = (
                    current_value is None or
                    current_value == "" or
                    (isinstance(current_value, str) and not current_value.strip()) or
                    (isinstance(current_value, float) and pd.isna(current_value))
            )

            is_rec_useful = (
                    rec_value and
                    not (isinstance(rec_value, str) and not rec_value.strip()) and
                    not (isinstance(rec_value, float) and pd.isna(rec_value))
            )

            if is_empty and is_rec_useful:
                final_metadata[key] = rec_value

        # Handle authors separately
        if 'authors' not in final_metadata or not final_metadata['authors']:
            if 'authors' in recommendation_data and recommendation_data['authors']:
                final_metadata['authors'] = recommendation_data['authors']

        # Handle relations separately
        if 'dct:relation' not in final_metadata or not final_metadata['dct:relation']:
            if 'dct:relation' in recommendation_data and recommendation_data['dct:relation']:
                final_metadata['dct:relation'] = recommendation_data['dct:relation']

        self.internal_records[name] = final_metadata
        metadata_to_load = final_metadata

        # Clear simple metadata fields
        for key, field_info in self.metadata_fields.items():
            widget = field_info['widget']
            field_type = field_info['type']
            if field_type == 'text':
                widget.delete("1.0", tk.END)
            else:  # entry
                widget.delete(0, tk.END)

        # Load simple metadata fields
        for key, field_info in self.metadata_fields.items():
            widget = field_info['widget']
            field_type = field_info['type']
            value = metadata_to_load.get(key, "")

            if isinstance(value, list):
                value = "\n".join(value)

            if pd.isna(value):
                value = ""

            if field_type == 'text':
                widget.insert("1.0", str(value))
            else:  # entry
                widget.insert(0, str(value))

        # Clear and reload relation fields
        self.clear_relation_fields()

        # Get relations using the proper key from JSON
        relations = metadata_to_load.get('dct:relation', [])

        # Handle string format (split by newlines) for backward compatibility
        if isinstance(relations, str):
            relations = [r.strip() for r in relations.split('\n') if r.strip()]

        # Ensure relations is a list
        if not isinstance(relations, list):
            relations = []

        if not relations:
            # Add at least one empty relation field
            self.add_relation_field()
        else:
            for relation in relations:
                self.add_relation_field(relation)

        # Clear and reload author fields
        self.clear_author_fields()
        authors = metadata_to_load.get('authors', [])

        if not authors:
            # Add at least one empty author field
            self.add_author_field()
        else:
            for author in authors:
                name = author.get('name', '')
                affiliations = author.get('affiliations', [])
                self.add_author_field(name=name, affiliations=affiliations)

        self.file_label.config(text=f"File {self.current_index + 1} of {len(self.pdf_files)}: {name}")

        self.display_pdf(pdf_path)
        self.extract_and_display_text(pdf_path)

        self.current_metadata = metadata_to_load

    def display_pdf(self, pdf_path):
        self.current_pdf_path = pdf_path
        self.dpi = 150
        self.render_pdf_page()

    def extract_and_display_text(self, pdf_path):
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text_content = ""
                self.total_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages[:2]):
                    text_content += f"\n--- Page {i + 1} ---\n"
                    text_content += page.extract_text() or "[No text found on this page]"
                    text_content += "\n"

            self.extracted_text_widget.delete("1.0", tk.END)
            self.extracted_text_widget.insert("1.0", text_content)
        except Exception as e:
            self.total_pages = 0
            self.extracted_text_widget.delete("1.0", tk.END)
            self.extracted_text_widget.insert("1.0", f"Error extracting text:\n{str(e)}")

    def render_pdf_page(self):
        if not self.current_pdf_path:
            return

        try:
            images = convert_from_path(
                self.current_pdf_path,
                dpi=self.dpi,
                first_page=1,
                last_page=2
            )

            if not images:
                self.pdf_canvas.delete("all")
                self.page_label.config(text="No pages in PDF")
                return

            if len(images) == 2:
                img1, img2 = images[0], images[1]
                width = max(img1.width, img2.width)
                height = img1.height + img2.height

                combined_image = Image.new('RGB', (width, height), 'white')
                combined_image.paste(img1, (0, 0))
                combined_image.paste(img2, (0, img1.height))
                final_image = combined_image
            else:
                final_image = images[0]

            # Get canvas width and scale image to fit
            canvas_width = self.pdf_canvas.winfo_width()
            if canvas_width > 1:  # Only scale if canvas has been drawn
                scale_factor = canvas_width / final_image.width
                new_width = int(final_image.width * scale_factor)
                new_height = int(final_image.height * scale_factor)
                final_image = final_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            self.pdf_photo_image = ImageTk.PhotoImage(final_image)

            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_image(0, 0, image=self.pdf_photo_image, anchor=tk.NW)
            self.pdf_canvas.config(scrollregion=self.pdf_canvas.bbox("all"))

            self.page_label.config(text=f"Showing Pages 1-{len(images)}")

        except Exception as e:
            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_text(400, 300,
                                        text=f"Error rendering PDF:\n{e}\n\nIs Poppler installed and in your PATH?",
                                        fill="red", width=500)
            print(f"Error rendering page: {e}")

    def zoom_in(self):
        self.dpi += 30
        self.render_pdf_page()

    def zoom_out(self):
        if self.dpi > 50:
            self.dpi -= 30
            self.render_pdf_page()

    def fit_to_window(self):
        self.dpi = 150
        self.render_pdf_page()

    def on_canvas_press(self, event):
        self.canvas_x = self.pdf_canvas.canvasx(event.x)
        self.canvas_y = self.pdf_canvas.canvasy(event.y)
        self.pdf_canvas.config(cursor="fleur")

    def on_canvas_drag(self, event):
        self.pdf_canvas.scan_dragto(self.canvas_x, self.canvas_y, gain=1)

    def on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.pdf_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.pdf_canvas.yview_scroll(-1, "units")

    def extract_text_simple(self, pdf_path):
        try:
            text = extract_text(pdf_path)
            if text and len(text.strip()) > 50:
                return text
        except:
            pass
        try:
            reader = PdfReader(pdf_path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except:
            return ""

    def extract_bold_title(self, pdf_path, min_len=10, max_lines=5):
        title_lines = []
        try:
            for page_layout in extract_pages(pdf_path):
                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        for text_line in element:
                            if not isinstance(text_line, LTTextLine):
                                continue
                            bold_chars, total_chars = 0, 0
                            line_text = text_line.get_text().strip()
                            if not line_text or len(line_text) < min_len:
                                continue
                            for char in text_line:
                                if isinstance(char, LTChar):
                                    total_chars += 1
                                    if "Bold" in char.fontname or "bold" in char.fontname:
                                        bold_chars += 1
                            if total_chars > 0:
                                bold_ratio = bold_chars / total_chars
                                if bold_ratio > 0.6:
                                    title_lines.append(line_text)
                                elif title_lines:
                                    return " ".join(title_lines)
                break
        except:
            pass
        return " ".join(title_lines)

    def extract_dois(self, text):
        pattern = r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b'
        return list(set(re.findall(pattern, text)))

    def validate_dois(self, dois):
        valid_links = []
        for doi in dois:
            try:
                cr(doi)
                valid_links.append(f"https://doi.org/{doi}")
            except:
                continue
        return valid_links

    def guess_language(self, text):
        try:
            return detect(text)
        except:
            return "und"

    def extract_author_block(self, text):
        lines = text.strip().split('\n')
        author_lines = []
        found_title_idx = -1
        for i, line in enumerate(lines):
            if len(line.strip()) > 10 and len(line.split()) > 3:
                found_title_idx = i
                break
        if found_title_idx < 0:
            return []
        for j in range(found_title_idx + 1, found_title_idx + 6):
            if j < len(lines):
                l = lines[j].strip()
                if l and (re.search(r'\b[A-Z]\.?\s?[A-Z][a-z]+', l) or
                          re.search(r'\bUniversity\b|\bDortmund\b|\bInstitute\b|\bGermany\b', l) or
                          l.count(',') >= 1):
                    author_lines.append(l)
        return author_lines

    def extract_metadata_from_text(self, text, pdf_path, fallback_title="Unknown Title"):
        metadata = {}
        metadata['dct:title'] = self.extract_bold_title(pdf_path) or fallback_title
        metadata['dcat:contactPoint'] = ""
        metadata['dcat:keyword'] = ""
        metadata['dct:publisher'] = "DECHEMA"
        metadata['dcat:theme'] = "http://eurovoc.europa.eu/100142"
        metadata['dct:type'] = "http://purl.org/spar/fabio/Abstract"
        metadata['dct:issued'] = datetime.now().date().isoformat()

        # Extract DOIs and create relations list
        dois = self.validate_dois(self.extract_dois(text))
        metadata['dct:relation'] = dois  # Store as list with proper key

        metadata['dct:language'] = self.guess_language(text)

        # Extract author information
        author_lines = self.extract_author_block(text)
        authors = []
        if author_lines:
            # Simple heuristic: lines with names vs lines with affiliations
            for line in author_lines:
                if re.search(r'\b[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+', line):
                    # Likely a name
                    name_match = re.search(r'[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+', line)
                    if name_match:
                        authors.append({
                            'name': name_match.group(),
                            'affiliations': []
                        })
                elif authors:
                    # Likely an affiliation for the last author
                    authors[-1]['affiliations'].append(line)

        metadata['authors'] = authors
        return metadata

    def prev_file(self):
        if self.current_index > 0:
            self.save_current_metadata()
            self.current_index -= 1
            self.load_current_file()

    def next_file(self):
        if self.current_index < len(self.pdf_files) - 1:
            self.save_current_metadata()
            self.current_index += 1
            self.load_current_file()
        else:
            messagebox.showinfo("End", "You've reached the last file")

    def go_to_pdf(self):
        if not self.pdf_files:
            messagebox.showwarning("No Files", "No PDF files loaded.")
            return

        try:
            index = int(self.goto_entry.get()) - 1
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number.")
            return

        if index < 0 or index >= len(self.pdf_files):
            messagebox.showwarning("Out of Range", f"Enter a number between 1 and {len(self.pdf_files)}.")
            return

        self.save_current_metadata()
        self.current_index = index
        self.load_current_file()

    def collect_gui_metadata(self):
        collected_data = {}

        # Collect simple metadata fields
        for key, field_info in self.metadata_fields.items():
            widget = field_info['widget']
            field_type = field_info['type']

            if field_type == 'text':
                value = widget.get("1.0", tk.END).strip()
            else:  # entry
                value = widget.get().strip()

            collected_data[key] = value if value else ""

        # Collect relations - store with proper key
        relations = []
        for rel_widget in self.relation_entries:
            rel_text = rel_widget['entry'].get().strip()
            if rel_text:  # Only add non-empty relations
                relations.append(rel_text)
        collected_data['dct:relation'] = relations  # Changed from 'relations' to 'dct:relation'

        # Collect authors
        authors = []
        for widget in self.author_widgets:
            name = widget['name'].get().strip()

            # Collect affiliations from individual entry fields
            affiliations = []
            for aff_widget in widget['affiliation_entries']:
                aff_text = aff_widget['entry'].get().strip()
                if aff_text:  # Only add non-empty affiliations
                    affiliations.append(aff_text)

            if name:  # Only add if name is not empty
                authors.append({
                    'name': name,
                    'affiliations': affiliations
                })

        collected_data['authors'] = authors

        if hasattr(self, 'pdf_files') and self.pdf_files:
            current_file = self.pdf_files[self.current_index]
            basename = os.path.splitext(os.path.basename(current_file))[0]
            collected_data['file_title'] = basename

        return collected_data

    def save_current_metadata(self):
        if not hasattr(self, 'pdf_files') or not self.pdf_files:
            return

        current_file = self.pdf_files[self.current_index]
        basename = os.path.splitext(os.path.basename(current_file))[0]

        if not self.internal_records.get(basename):
            self.internal_records[basename] = {"file_title": basename}

        new_data = self.collect_gui_metadata()
        old_data = self.internal_records[basename]

        if new_data != old_data:
            self.internal_records[basename].update(new_data)
            self.user_modified.add(basename)

    def finish_and_save(self):
        if not self.internal_records:
            messagebox.showwarning("No Data", "Nothing to save.")
            return

        # Save current file before finishing
        self.save_current_metadata()

        # Convert internal records to list
        output_data = list(self.internal_records.values())

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = f"metadata_output_{timestamp}.json"

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)

            messagebox.showinfo("Saved", f"Saved to {os.path.basename(output_path)}.\n"
                                         f"{len(self.user_modified)} entries updated.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON file: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MetadataExtractorGUI(root)
    root.mainloop()