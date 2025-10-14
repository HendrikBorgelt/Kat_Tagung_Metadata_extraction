import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import glob
from datetime import datetime
from langdetect import detect
import re
import pandas as pd
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTTextLine
from crossref.restful import Works as Crossref
import fitz  # PyMuPDF for PDF display
import pdfplumber

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

    def create_widgets(self):
        # Top frame for file selection
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Button(top_frame, text="Select PDF Folder", command=self.select_folder).pack(side=tk.LEFT, padx=5)
        self.folder_label = ttk.Label(top_frame, text="No folder selected")
        self.folder_label.pack(side=tk.LEFT, padx=5)

        # Main content frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - Metadata fields
        left_frame = ttk.LabelFrame(main_frame, text="Metadata Fields", width=400)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        left_frame.pack_propagate(False)

        # Scrollable metadata area
        canvas = tk.Canvas(left_frame, bg='white')
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.metadata_fields = {}

        metadata_keys = [
            'dct:title', 'dcat:contactPoint', 'foaf:agent',
            'dcat:keyword', 'dct:publisher', 'dcat:theme',
            'dct:type', 'dct:language', 'dct:relation'
        ]

        for key in metadata_keys:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, padx=5, pady=5)

            label = ttk.Label(frame, text=key, font=("Arial", 9, "bold"))
            label.pack(anchor=tk.W)

            entry = tk.Text(frame, height=3, width=40, wrap=tk.WORD)
            entry.pack(fill=tk.BOTH, expand=True)

            self.metadata_fields[key] = entry

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right panel - Split into PDF preview and text extraction
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Notebook for tabs
        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: PDF Preview
        pdf_tab = ttk.Frame(notebook)
        notebook.add(pdf_tab, text="PDF Preview")

        # PDF controls
        pdf_control_frame = ttk.Frame(pdf_tab)
        pdf_control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Button(pdf_control_frame, text="Zoom In (+)", command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        ttk.Button(pdf_control_frame, text="Zoom Out (-)", command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(pdf_control_frame, text="Fit to Window", command=self.fit_to_window).pack(side=tk.LEFT, padx=2)

        self.page_label = ttk.Label(pdf_control_frame, text="Page 1/1")
        self.page_label.pack(side=tk.LEFT, padx=20)

        # PDF canvas with scrollbars
        pdf_container = ttk.Frame(pdf_tab)
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

        # Bind mouse events for panning
        self.pdf_canvas.bind("<Button-1>", self.on_canvas_press)
        self.pdf_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.pdf_canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.pdf_canvas.bind("<Button-4>", self.on_mousewheel)
        self.pdf_canvas.bind("<Button-5>", self.on_mousewheel)

        # Tab 2: Extracted Text
        text_tab = ttk.Frame(notebook)
        notebook.add(text_tab, text="Extracted Text")

        text_label = ttk.Label(text_tab, text="Copy text from here to metadata fields:", font=("Arial", 9, "bold"))
        text_label.pack(anchor=tk.W, padx=5, pady=5)

        self.extracted_text_widget = tk.Text(text_tab, wrap=tk.WORD, bg='white')
        text_scrollbar = ttk.Scrollbar(text_tab, orient=tk.VERTICAL, command=self.extracted_text_widget.yview)
        self.extracted_text_widget.config(yscrollcommand=text_scrollbar.set)

        self.extracted_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Initialize variables
        self.zoom_level = 1.5
        self.current_page = 0
        self.pdf_doc = None
        self.canvas_x = 0
        self.canvas_y = 0

        # Bottom frame - Navigation
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        ttk.Button(bottom_frame, text="◀ Previous", command=self.prev_file).pack(side=tk.LEFT, padx=2)
        self.file_label = ttk.Label(bottom_frame, text="No files loaded")
        self.file_label.pack(side=tk.LEFT, padx=20, expand=True)
        ttk.Button(bottom_frame, text="Next ▶", command=self.next_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom_frame, text="Finish & Save", command=self.finish_and_save).pack(side=tk.LEFT, padx=2)

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select folder with PDF files")
        if folder:
            self.pdf_files = glob.glob(os.path.join(folder, "**", "*.pdf"), recursive=True)
            if self.pdf_files:
                self.folder_label.config(text=f"{len(self.pdf_files)} PDFs found")
                self.current_index = 0
                self.load_current_file()
            else:
                messagebox.showwarning("No Files", "No PDF files found in selected folder")

    def load_current_file(self):
        if not self.pdf_files:
            return

        pdf_path = self.pdf_files[self.current_index]
        name = os.path.splitext(os.path.basename(pdf_path))[0]

        # Extract metadata
        text = self.extract_text_simple(pdf_path)
        metadata = self.extract_metadata_from_text(text, pdf_path, fallback_title=name)
        metadata["file_title"] = name

        # Clear old entries
        for field in self.metadata_fields.values():
            field.delete("1.0", tk.END)

        # Populate fields
        for key, field in self.metadata_fields.items():
            value = metadata.get(key, "")
            if isinstance(value, list):
                value = "\n".join(value)
            field.insert("1.0", str(value))

        # Update label
        self.file_label.config(text=f"File {self.current_index + 1} of {len(self.pdf_files)}: {name}")

        # Display PDF and extract text
        self.display_pdf(pdf_path)
        self.extract_and_display_text(pdf_path)

        # Store current metadata for saving
        self.current_metadata = metadata

    def display_pdf(self, pdf_path):
        try:
            if self.pdf_doc:
                self.pdf_doc.close()
            self.pdf_doc = fitz.open(pdf_path)
            self.current_page = 0
            self.zoom_level = 1.5
            self.render_pdf_page()
        except Exception as e:
            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_text(200, 50, text=f"Error loading PDF:\n{str(e)}", fill="red")

    def extract_and_display_text(self, pdf_path):
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text_content = ""
                for i, page in enumerate(pdf.pages[:2]):  # Extract first 2 pages
                    text_content += f"\n--- Page {i + 1} ---\n"
                    text_content += page.extract_text() or "[No text found on this page]"
                    text_content += "\n"

            self.extracted_text_widget.delete("1.0", tk.END)
            self.extracted_text_widget.insert("1.0", text_content)
        except Exception as e:
            self.extracted_text_widget.delete("1.0", tk.END)
            self.extracted_text_widget.insert("1.0", f"Error extracting text:\n{str(e)}")

    def render_pdf_page(self):
        if not self.pdf_doc:
            return

        try:
            # Get first two pages and merge them
            num_pages = len(self.pdf_doc)
            pages_to_render = min(2, num_pages)

            pixmaps = []
            for i in range(pages_to_render):
                page = self.pdf_doc[i]
                pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom_level, self.zoom_level))
                pixmaps.append(pix)

            # Merge pages vertically
            if len(pixmaps) == 2:
                total_height = pixmaps[0].height + pixmaps[1].height
                width = max(pixmaps[0].width, pixmaps[1].width)

                # Create new image with combined height
                combined_pix = fitz.Pixmap(fitz.csRGB, fitz.Rect(0, 0, width, total_height))
                combined_pix.clear_with(255)  # White background

                # Paste first page
                combined_pix.paste(pixmaps[0], (0, 0))
                # Paste second page below first
                combined_pix.paste(pixmaps[1], (0, pixmaps[0].height))

                img_data = combined_pix.tobytes("ppm")
            else:
                img_data = pixmaps[0].tobytes("ppm")

            self.pdf_image = tk.PhotoImage(data=img_data)

            self.pdf_canvas.delete("all")
            self.pdf_canvas.create_image(0, 0, image=self.pdf_image, anchor=tk.NW)
            self.pdf_canvas.config(scrollregion=self.pdf_canvas.bbox("all"))

            self.page_label.config(text=f"Page 1-{pages_to_render}/{num_pages}")
        except Exception as e:
            print(f"Error rendering page: {e}")

    def zoom_in(self):
        self.zoom_level *= 1.2
        self.render_pdf_page()

    def zoom_out(self):
        self.zoom_level /= 1.2
        self.render_pdf_page()

    def fit_to_window(self):
        self.zoom_level = 1.5
        self.render_pdf_page()

    def on_canvas_press(self, event):
        self.canvas_x = event.x
        self.canvas_y = event.y

    def on_canvas_drag(self, event):
        dx = self.canvas_x - event.x
        dy = self.canvas_y - event.y
        self.pdf_canvas.xview_scroll(dx, "units")
        self.pdf_canvas.yview_scroll(dy, "units")
        self.canvas_x = event.x
        self.canvas_y = event.y

    def on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.zoom_out()
        elif event.num == 4 or event.delta > 0:
            self.zoom_in()

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

    def extract_underlined_author(self, pdf_path, full_text=None):
        text = self.extract_text_simple(pdf_path)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        candidate_lines = [l for l in lines[:30] if re.search(r'[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+', l)]
        if candidate_lines:
            candidate_lines.sort(key=lambda x: len(x))
            return re.findall(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", candidate_lines[0])[0]
        if full_text:
            lines = full_text.strip().split("\n")
            for line in lines[:20]:
                if re.search(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", line):
                    return re.search(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", line).group()
        return "Not found"

    def extract_author_block(self, text):
        lines = text.strip().split('\n')
        author_block = []
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
                    author_block.append(l)
        return author_block

    def extract_metadata_from_text(self, text, pdf_path, fallback_title="Unknown Title"):
        metadata = {}
        metadata['dct:title'] = self.extract_bold_title(pdf_path) or fallback_title
        metadata['dcat:contactPoint'] = self.extract_underlined_author(pdf_path)
        metadata['dcat:keyword'] = ""
        metadata['dct:publisher'] = "DECHEMA"
        metadata['dcat:theme'] = "http://eurovoc.europa.eu/100142"
        metadata['dct:type'] = "http://purl.org/spar/fabio/Abstract"
        metadata['dct:issued'] = datetime.now().date().isoformat()
        metadata['dct:relation'] = self.validate_dois(self.extract_dois(text))
        metadata['dct:language'] = self.guess_language(text)
        author_lines = self.extract_author_block(text)
        metadata['foaf:agent'] = "; ".join(author_lines)
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

    def save_current_metadata(self):
        if hasattr(self, 'current_metadata'):
            for key, field in self.metadata_fields.items():
                value = field.get("1.0", tk.END).strip()
                self.current_metadata[key] = value if value else ""
            self.records.append(self.current_metadata)

    def finish_and_save(self):
        self.save_current_metadata()

        if not self.records:
            messagebox.showwarning("No Data", "No metadata to save")
            return

        try:
            df = pd.DataFrame(self.records)
            cols = ["file_title"] + [c for c in df.columns if c != "file_title"]
            df = df[cols]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = f"metadata_output_{timestamp}.xlsx"
            df.to_excel(output_path, index=False, engine="openpyxl")

            messagebox.showinfo("Success", f"Metadata saved to {output_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MetadataExtractorGUI(root)
    root.mainloop()