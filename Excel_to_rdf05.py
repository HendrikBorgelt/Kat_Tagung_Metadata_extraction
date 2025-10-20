import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef
from rdflib.namespace import DCTERMS, RDFS
import re
from urllib.parse import urlparse, quote

# === 1. Load Excel file ===
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
            pass

    # Fallback: treat as plain literal
    return Literal(s)


def name_to_uri(name: str) -> URIRef:
    """Generate a readable and URI-safe identifier for a name."""
    clean = name.strip()
    clean = re.sub(r"[^A-Za-z0-9\s._-]", "", clean)
    clean = clean.replace(".", "").replace(" ", "_")
    return EX[quote(clean)]


def add_foaf_agent(abstract_uri, agent_name: str):
    """Create and add a FOAF Agent resource with label."""
    agent_uri = name_to_uri(agent_name)
    g.add((agent_uri, RDF.type, FOAF.Agent))
    g.add((agent_uri, RDFS.label, Literal(agent_name.strip())))
    return agent_uri


def parse_organization(org_string: str) -> dict:
    """
    Parse organization string into components (name, address, location).

    Attempts to extract organization name, street address, and location/city
    by splitting on commas. Returns a dict with keys: 'name', 'address', 'location'.
    Falls back to treating entire string as name if parsing is ambiguous.

    Example: "Max Planck Institute, Mainz, Germany"
    -> {'name': 'Max Planck Institute', 'location': 'Mainz, Germany', 'address': None}

    Example: "Department of Chemistry, University of Berlin, Humboldt Street 5, Berlin, Germany"
    -> {'name': 'Department of Chemistry, University of Berlin', 'address': 'Humboldt Street 5', 'location': 'Berlin, Germany'}
    """
    parts = [p.strip() for p in org_string.split(",")]

    result = {
        'name': org_string.strip(),
        'address': None,
        'location': None
    }

    # If only 1 part, return as name only
    if len(parts) == 1:
        return result

    # If 2 parts: assume "Name, Location"
    if len(parts) == 2:
        result['name'] = parts[0]
        result['location'] = parts[1]
        return result

    # If 3+ parts: try to detect address pattern
    # Heuristic: if a part contains a digit, likely an address (e.g., "Street 5")
    has_digit_index = None
    for i, part in enumerate(parts):
        if any(char.isdigit() for char in part):
            has_digit_index = i
            break

    if has_digit_index is not None and has_digit_index > 0:
        # Parts before digit index = organization name
        # Part with digit = address
        # Parts after = location
        result['name'] = ", ".join(parts[:has_digit_index])
        result['address'] = parts[has_digit_index]
        result['location'] = ", ".join(parts[has_digit_index + 1:]) if has_digit_index + 1 < len(parts) else None
    else:
        # No clear address pattern detected; treat first part as name, rest as location
        result['name'] = parts[0]
        result['location'] = ", ".join(parts[1:])

    return result


def add_organization_with_details(abstract_uri, org_string: str, pred):
    """
    Create and add an organization resource with address and location details.
    Uses FOAF and schema.org properties to represent the organization structure.
    """
    parsed = parse_organization(org_string)

    org_uri = name_to_uri(parsed['name'])
    g.add((abstract_uri, pred, org_uri))
    g.add((org_uri, RDF.type, SCHEMA.Organization))
    g.add((org_uri, RDFS.label, Literal(parsed['name'].strip())))

    # Add address if available (using schema.org PostalAddress)
    if parsed['address']:
        addr_uri = EX[quote(f"{name_to_uri(parsed['name']).split('/')[-1]}_address")]
        g.add((org_uri, SCHEMA.address, addr_uri))
        g.add((addr_uri, RDF.type, SCHEMA.PostalAddress))
        g.add((addr_uri, SCHEMA.streetAddress, Literal(parsed['address'].strip())))

    # Add location if available (using both schema.org and FOAF)
    if parsed['location']:
        # Use schema.org location as primary
        g.add((org_uri, SCHEMA.location, Literal(parsed['location'].strip())))
        # Optionally also add FOAF-based location
        g.add((org_uri, FOAF.based_near, Literal(parsed['location'].strip())))


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

            # === Split multiple entries ===
            if prefix == "foaf":
                # Authors separated by commas
                entries = [v.strip() for v in str(value).split(",") if v.strip()]
            else:
                # Everything else separated by semicolons
                entries = [v.strip() for v in str(value).split(";") if v.strip()]

            for entry in entries:
                # --- Handle FOAF Agents (authors/contributors) ---
                if col_name.lower() == "foaf:agent":
                    agent_uri = add_foaf_agent(abstract_uri, entry)
                    g.add((abstract_uri, DCT.contributor, agent_uri))

                # --- Handle DCAT Contact Point (also a FOAF Agent) ---
                elif col_name.lower() == "dcat:contactpoint":
                    agent_uri = add_foaf_agent(abstract_uri, entry)
                    g.add((abstract_uri, DCAT.contactPoint, agent_uri))

                # --- Handle Organizations ---
                elif col_name.lower().startswith("schema") and "organization" in col_name.lower():
                    add_organization_with_details(abstract_uri, entry, pred)

                # --- Default behavior ---
                else:
                    obj = interpret_value(entry)
                    g.add((abstract_uri, pred, obj))

# === 6. Serialize to Turtle ===
output_file = "abstracts_katalytikertagung.ttl"
g.serialize(destination=output_file, format="turtle")

print(f"✅ RDF graph written to {output_file}")