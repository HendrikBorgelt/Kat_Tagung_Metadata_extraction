import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef
from rdflib.namespace import DCTERMS, RDFS
import re
from urllib.parse import urlparse

# === 1. Load Excel file ===
# excel_path = "test for ttl conversion.xlsx"
excel_path = "metadata_output_for_conversion_20251014_1508.xlsx"
df = pd.read_excel(excel_path)

# Remove the 'file_title' column if it exists
if 'file_title' in df.columns:
    df = df.drop(columns=['file_title'])

# === 2. Define Namespaces ===
EX = Namespace("http://example.org/katalytikertagung/")
DCT = DCTERMS
SCHEMA = Namespace("https://schema.org/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
DCAT = Namespace("https://www.w3.org/ns/dcat#")

# === 3. Initialize Graph ===
g = Graph()
g.bind("ex", EX)
g.bind("dct", DCT)
g.bind("rdfs", RDFS)
g.bind("schema", SCHEMA)
g.bind("foaf", FOAF)
g.bind("dcat", DCAT)

# === 4. Create central instance ===
central = EX["Abstracts_der_58_Katalytikertagung"]
g.add((central, RDF.type, EX["ConferenceAbstractCollection"]))
g.add((central, DCT.title, Literal("Abstracts der 58. Katalytikertagung", lang="de")))


# === Helper: URI failsafe ===
def is_valid_uri(uri: str) -> bool:
    """Check if string looks like a valid absolute URI (failsafe)."""
    try:
        result = urlparse(uri)
        # valid if scheme (http/https) and netloc exist and no commas/spaces
        return all([result.scheme in ("http", "https"), result.netloc]) and ("," not in uri) and (" " not in uri)
    except Exception:
        return False


def interpret_value(value):
    """Return URIRef if value looks like a valid standalone URI or DOI; else Literal."""
    s = str(value).strip()

    # Normalize DOI formats
    if re.match(r"^(doi:|10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", s, re.IGNORECASE):
        if s.lower().startswith("doi:"):
            s = "https://doi.org/" + s[4:].strip()
        elif re.match(r"^10\.\d{4,9}/", s):
            s = "https://doi.org/" + s

    # Validate URI syntax
    if is_valid_uri(s):
        try:
            return URIRef(s)
        except Exception:
            pass  # if rdflib still rejects, fall back to Literal

    # Fallback: treat as plain literal
    return Literal(s)


# === 5. Iterate through rows and add RDF triples ===
for idx, row in df.iterrows():
    abstract_uri = EX[f"abstract_{idx + 1}"]
    g.add((central, EX.has_abstract, abstract_uri))
    g.add((abstract_uri, RDF.type, EX.Abstract))

    for col_name, value in row.items():
        if pd.notna(value):
            col_name = col_name.strip()

            # Detect prefix and assign appropriate namespace
            if ":" in col_name:
                prefix, local = col_name.split(":", 1)
                prefix = prefix.lower()
                if prefix == "dct":
                    pred = DCT[local]
                elif prefix == "schema":
                    pred = SCHEMA[local]
                elif prefix == "foaf":
                    pred = FOAF[local]
                elif prefix == "dcat":
                    pred = DCAT[local]
                elif prefix == "ex":
                    pred = EX[local]
                else:
                    pred = EX[local]
            else:
                pred = EX[col_name.replace(" ", "_")]

            # === Split multiple entries separated by ";" ===
            entries = [v.strip() for v in str(value).split(";") if v.strip()]
            for entry in entries:
                obj = interpret_value(entry)

                # Typed organization node handling
                if col_name.lower().startswith("schema") and "organization" in col_name.lower():
                    org_uri = URIRef(f"{EX}organization_{abs(hash(entry))}")
                    g.add((abstract_uri, pred, org_uri))
                    g.add((org_uri, RDF.type, SCHEMA.Organization))
                    g.add((org_uri, RDFS.label, obj))
                else:
                    g.add((abstract_uri, pred, obj))

# === 6. Serialize to Turtle ===
output_file = "abstracts_katalytikertagung.ttl"
g.serialize(destination=output_file, format="turtle")

print(f"✅ RDF graph written to {output_file}")
