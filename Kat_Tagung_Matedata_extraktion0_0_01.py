from habanero import Crossref
from langdetect import detect
from datetime import datetime
import fitz
import re
import numpy as np

# Configure Crossref
cr = Crossref()

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    return "\n".join([page.get_text() for page in doc])

def extract_dois(text):
    pattern = r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b'
    return list(set(re.findall(pattern, text)))

def validate_dois(dois):
    valid_links = []
    for doi in dois:
        try:
            cr.works(ids=doi)  # Validates
            valid_links.append(f"https://doi.org/{doi}")
        except:
            continue
    return valid_links

def guess_language(text):
    try:
        return detect(text)
    except:
        return "und"


def extract_underlined_author(pdf_path, full_text=None):
    """
    Tries to extract the underlined author from:
    1. Underlined span flags
    2. Drawn underline geometry
    3. Fallback: first author from author block
    """
    doc = fitz.open(pdf_path)

    # --- Method 1: Underlined spans ---
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("flags", 0) & 8:
                        text = span["text"].strip()
                        if re.match(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", text):
                            return text

    # --- Method 2: Drawing geometry (underlines) ---
    for page in doc:
        drawings = page.get_drawings()
        underline_y_coords = []

        for d in drawings:
            if d["type"] == "line":
                p1, p2 = d["points"]
                y1, y2 = p1[1], p2[1]
                if abs(y1 - y2) < 1.0:  # horizontal line
                    underline_y_coords.append(y1)

        if not underline_y_coords:
            continue

        y_coords = list(np.unique(np.round(underline_y_coords, 1)))

        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text_y = span["bbox"][1]
                    for uy in y_coords:
                        if 0 < uy - text_y < 15:
                            text = span["text"].strip()
                            if re.match(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", text):
                                return text

    # --- Method 3: First author from author block ---
    if full_text:
        lines = full_text.strip().split("\n")
        # Find title index
        title_idx = next((i for i, line in enumerate(lines) if len(line.strip()) > 10 and len(line.split()) > 3), -1)

        # Try next few lines for author block
        for i in range(title_idx + 1, min(title_idx + 6, len(lines))):
            line = lines[i].strip()
            if re.search(r'[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+', line):  # Looks like names
                # Return first matching name-like token
                match = re.search(r"[A-Z][a-z]+(?:\s[A-Z]\.?)?\s[A-Z][a-z]+", line)
                if match:
                    return match.group()

    return "Not found"

def extract_underlined_text(pdf_path):
    doc = fitz.open(pdf_path)
    underlined = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    # Check for underline flag (bit 4 = 8)
                    if span.get("flags", 0) & 8:
                        underlined.append(span["text"].strip())
    return underlined

def extract_author_block(text):
    """
    Extracts the author/affiliation block between the title and the first paragraph of the body.
    """
    lines = text.strip().split('\n')
    author_block = []
    title_found = False
    found_title_idx = -1

    # Step 1: Find the title line (non-empty, reasonably long)
    for i, line in enumerate(lines):
        if len(line.strip()) > 10 and len(line.split()) > 3:
            found_title_idx = i
            title_found = True
            break

    if not title_found:
        return []

    # Step 2: Collect next 1–3 non-empty lines that contain name-like patterns or institutions
    for j in range(found_title_idx + 1, found_title_idx + 6):  # Look at 5 lines max
        if j < len(lines):
            l = lines[j].strip()
            if not l:
                continue
            if (
                re.search(r'\b[A-Z]\.?\s?[A-Z][a-z]+', l)  # initials or full names
                or re.search(r'\bUniversity\b|\bDortmund\b|\bInstitute\b|\bGermany\b', l)
                or l.count(',') >= 1
            ):
                author_block.append(l)

    return author_block

def extract_metadata_from_text(text, pdf_path, fallback_title="Unknown Title"):
    metadata = {}
    underlined_names = extract_underlined_text(pdf_path)
    # Basic heuristics
    metadata['dct:title'] = re.findall(r"(?<=\n)[^\n]{20,100}(?=\n)", text)[0].strip() if re.findall(r"(?<=\n)[^\n]{20,100}(?=\n)", text) else fallback_title
    metadata['dcat:contactPoint'] = extract_underlined_author(pdf_path)
    metadata['dcat:keyword'] = ""  # You may adjust this or use NLP
    metadata['dct:publisher'] = "DECHEMA, Gesellschaft für Chemische Technik und Biotechnologie e.V."
    metadata['dcat:theme'] = "http://eurovoc.europa.eu/100142"
    metadata['dct:type'] = "http://purl.org/spar/fabio/Abstract"
    metadata['dct:issued'] = datetime.now().date().isoformat()
    metadata['dct:relation'] = validate_dois(extract_dois(text))
    metadata['dct:language'] = guess_language(text)
    author_lines = extract_author_block(text)
    metadata['foaf:agent'] = "; ".join(author_lines)

    return metadata

# Paths to the uploaded PDFs
pdf_files = {
    "Abstract_ServicesAndTools": "D:/D_smhhborg/sciebo/Borgelt_Scibo/07 Paper & Veroeffentlichungen/02_Abstracts/Abstract_ServicesAndTools.pdf",
    "KatTagung": "D:/D_smhhborg/sciebo/Borgelt_Scibo/07 Paper & Veroeffentlichungen/02_Abstracts//KatTagung.pdf",
    "PEMT_HB": "D:/D_smhhborg/sciebo/Borgelt_Scibo/07 Paper & Veroeffentlichungen/02_Abstracts/PEMT_HB_20240510.pdf"
}

# Extract and print metadata
for name, path in pdf_files.items():
    print(f"\n Metadata for {name}")
    text = extract_text(path)
    metadata = extract_metadata_from_text(text, path, fallback_title=name)
    for key, value in metadata.items():
        print(f"{key}: {value}")
