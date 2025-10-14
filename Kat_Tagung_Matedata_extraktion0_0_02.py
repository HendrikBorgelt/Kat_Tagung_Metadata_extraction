from langdetect import detect
from datetime import datetime
from crossref.restful import Works as Crossref
import re
import numpy as np
from io import StringIO
from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTTextLine
from PyPDF2 import PdfReader
import pandas as pd
import os
import glob
from datetime import datetime

# Configure Crossref
cr = Crossref()


def extract_text_simple(pdf_path):
    """Extract text using pdfminer, with PyPDF2 fallback."""
    try:
        text = extract_text(pdf_path)
        if text and len(text.strip()) > 50:
            return text
    except Exception:
        pass
    # fallback
    try:
        reader = PdfReader(pdf_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def extract_dois(text):
    pattern = r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b'
    return list(set(re.findall(pattern, text)))


def validate_dois(dois):
    valid_links = []
    for doi in dois:
        try:
            cr(doi)  # Validate via Crossref REST API
            valid_links.append(f"https://doi.org/{doi}")
        except Exception:
            continue
    return valid_links


def guess_language(text):
    try:
        return detect(text)
    except Exception:
        return "und"


def extract_underlined_author(pdf_path, full_text=None):
    """
    Fallback heuristic for extracting the underlined author without fitz.
    Tries to guess the 'highlighted' author by position or typical formatting patterns.
    """
    # Without access to drawing/flags, approximate based on line proximity.
    text = extract_text_simple(pdf_path)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Try to detect author-like names in the first 30 lines
    candidate_lines = [l for l in lines[:30] if re.search(r'[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+', l)]
    if candidate_lines:
        # pick the shortest or first line with several capitalized names
        candidate_lines.sort(key=lambda x: len(x))
        return re.findall(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", candidate_lines[0])[0]

    # fallback: from author block
    if full_text:
        lines = full_text.strip().split("\n")
        for line in lines[:20]:
            if re.search(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", line):
                return re.search(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", line).group()
    return "Not found"


def extract_underlined_text(pdf_path):
    """
    Dummy replacement for underlined text extraction.
    Since fitz is not used, we return potential emphasis candidates:
    short text fragments in uppercase or between underscores.
    """
    text = extract_text_simple(pdf_path)
    underlined = re.findall(r'_[^_]+_|[A-Z]{3,}(?:\s[A-Z]{3,})*', text)
    return [u.strip("_").strip() for u in underlined]


def extract_author_block(text):
    """
    Extracts the author/affiliation block between the title and the first paragraph.
    """
    lines = text.strip().split('\n')
    author_block = []
    title_found = False
    found_title_idx = -1

    for i, line in enumerate(lines):
        if len(line.strip()) > 10 and len(line.split()) > 3:
            found_title_idx = i
            title_found = True
            break

    if not title_found:
        return []

    for j in range(found_title_idx + 1, found_title_idx + 6):
        if j < len(lines):
            l = lines[j].strip()
            if not l:
                continue
            if (
                    re.search(r'\b[A-Z]\.?\s?[A-Z][a-z]+', l)
                    or re.search(r'\bUniversity\b|\bDortmund\b|\bInstitute\b|\bGermany\b', l)
                    or l.count(',') >= 1
            ):
                author_block.append(l)
    return author_block


def extract_metadata_from_text(text, pdf_path, fallback_title="Unknown Title"):
    metadata = {}
    underlined_names = extract_underlined_text(pdf_path)
    metadata['dct:title'] = (
        re.findall(r"(?<=\n)[^\n]{20,100}(?=\n)", text)[0].strip()
        if re.findall(r"(?<=\n)[^\n]{20,100}(?=\n)", text)
        else fallback_title
    )
    metadata['dcat:contactPoint'] = extract_underlined_author(pdf_path)
    metadata['dcat:keyword'] = ""
    metadata['dct:publisher'] = "DECHEMA, Gesellschaft für Chemische Technik und Biotechnologie e.V."
    metadata['dcat:theme'] = "http://eurovoc.europa.eu/100142"
    metadata['dct:type'] = "http://purl.org/spar/fabio/Abstract"
    metadata['dct:issued'] = datetime.now().date().isoformat()
    metadata['dct:relation'] = validate_dois(extract_dois(text))
    metadata['dct:language'] = guess_language(text)
    author_lines = extract_author_block(text)
    metadata['foaf:agent'] = "; ".join(author_lines)
    return metadata


input_folders = [
    r"D:\D_smhhborg\sciebo\Borgelt_Scibo\07 Paper & Veroeffentlichungen\02_Abstracts",
    r"C:\Users\smhhborg\Documents\GitHub\Hendrik\Kat_Tagung_Metadata_extraction\58_KAT_Abstracts_NFDI4Cat"
]

# Collect all PDFs recursively from all input folders
pdf_files = []
for folder in input_folders:
    pdf_files.extend(glob.glob(os.path.join(folder, "**", "*.pdf"), recursive=True))

if not pdf_files:
    print("⚠️ No PDF files found in the given folder(s). Please check the paths.")
else:
    print(f"Found {len(pdf_files)} PDF file(s).")

# === Process files and extract metadata ===
records = []
for path in pdf_files:
    name = os.path.splitext(os.path.basename(path))[0]
    print(f"\nExtracting metadata for {name} ...")
    text = extract_text_simple(path)
    metadata = extract_metadata_from_text(text, path, fallback_title=name)
    metadata["file_title"] = name
    records.append(metadata)

# === Save to Excel ===
if records:
    df = pd.DataFrame(records)
    cols = ["file_title"] + [c for c in df.columns if c != "file_title"]
    df = df[cols]

    # Use timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = f"metadata_output_{timestamp}.xlsx"
    df.to_excel(output_path, index=False, engine="openpyxl")

    print(f"\n✅ Metadata successfully written to {output_path}")
else:
    print("No metadata records generated.")