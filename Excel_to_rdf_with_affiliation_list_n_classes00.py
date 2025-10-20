import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef, OWL
from rdflib.namespace import DCTERMS, RDFS
import re
from urllib.parse import urlparse, quote
from difflib import SequenceMatcher

# === CONFIGURATION ===
# Set to True to axiomatize dct:relation as an object property
AXIOMATIZE_DCT_RELATION = True  # Change to True if you want dct:relation as OWL object property

# === 1. Load Excel file ===
excel_path = "metadata_output_for_conversion_20251014_1508.xlsx"
df = pd.read_excel(excel_path)

# Remove the 'file_title' column if it exists
if 'file_title' in df.columns:
    df = df.drop(columns=['file_title'])

# === 2. Load affiliated organizations list ===
org_list_path = "list_of_affiliated_organisations.txt"
affiliated_orgs = pd.read_csv(org_list_path, sep="\t", encoding="utf-8")
affiliated_orgs.columns = affiliated_orgs.columns.str.strip()

# Create a lookup dictionary for fast matching
org_lookup = {}
for _, org_row in affiliated_orgs.iterrows():
    institution = str(org_row['INSTITUTION/COMPANY']).strip()
    address = str(org_row['FULL ADDRESS']).strip()
    org_lookup[institution.lower()] = {
        'name': institution,
        'address': address
    }

# === 3. Define Namespaces ===
EX = Namespace("http://example.org/katalytikertagung/")
DCT = DCTERMS
SCHEMA = Namespace("https://schema.org/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
DCAT = Namespace("https://www.w3.org/ns/dcat#")

# === 4. Initialize Graph ===
g = Graph()
g.bind("ex", EX)
g.bind("dct", DCT)
g.bind("rdfs", RDFS)
g.bind("schema", SCHEMA)
g.bind("foaf", FOAF)
g.bind("dcat", DCAT)
g.bind("owl", OWL)

# === 5. Define OWL Classes and Object Properties ===
# Define classes
g.add((EX.Abstract, RDF.type, OWL.Class))
g.add((EX.Abstract, RDFS.label, Literal("Abstract", lang="en")))
g.add((EX.Abstract, RDFS.comment, Literal("A conference abstract submitted to the Katalytikertagung", lang="en")))

g.add((FOAF.Agent, RDF.type, OWL.Class))
g.add((FOAF.Agent, RDFS.label, Literal("Agent", lang="en")))
g.add((FOAF.Agent, RDFS.comment, Literal("An author or contributor", lang="en")))

g.add((SCHEMA.Organization, RDF.type, OWL.Class))
g.add((SCHEMA.Organization, RDFS.label, Literal("Organization", lang="en")))
g.add((SCHEMA.Organization, RDFS.comment, Literal("An organization or institution", lang="en")))

# Define object properties for relations between these classes
g.add((DCT.contributor, RDF.type, OWL.ObjectProperty))
g.add((DCT.contributor, RDFS.label, Literal("contributor", lang="en")))
g.add((DCT.contributor, RDFS.comment, Literal("Links an abstract to its contributing agent/author", lang="en")))
g.add((DCT.contributor, RDFS.domain, EX.Abstract))
g.add((DCT.contributor, RDFS.range, FOAF.Agent))

g.add((DCAT.contactPoint, RDF.type, OWL.ObjectProperty))
g.add((DCAT.contactPoint, RDFS.label, Literal("contact point", lang="en")))
g.add((DCAT.contactPoint, RDFS.comment, Literal("Links an abstract to its contact person", lang="en")))
g.add((DCAT.contactPoint, RDFS.domain, EX.Abstract))
g.add((DCAT.contactPoint, RDFS.range, FOAF.Agent))

g.add((SCHEMA.sourceOrganization, RDF.type, OWL.ObjectProperty))
g.add((SCHEMA.sourceOrganization, RDFS.label, Literal("source organization", lang="en")))
g.add((SCHEMA.sourceOrganization, RDFS.comment, Literal("Links an abstract to its source organization", lang="en")))
g.add((SCHEMA.sourceOrganization, RDFS.domain, EX.Abstract))
g.add((SCHEMA.sourceOrganization, RDFS.range, SCHEMA.Organization))

# Optionally axiomatize dct:relation if configured
if AXIOMATIZE_DCT_RELATION:
    g.add((DCT.relation, RDF.type, OWL.ObjectProperty))
    g.add((DCT.relation, RDFS.label, Literal("relation", lang="en")))
    g.add((DCT.relation, RDFS.comment, Literal("A related resource", lang="en")))
    g.add((DCT.relation, RDFS.domain, EX.Abstract))
    g.add((DCT.relation, RDFS.range, EX.Abstract))

# Mark other commonly used properties as annotation properties
annotation_properties = [
    DCT.title,
    DCT.abstract,
    DCT.subject,
    DCT.date,
    DCT.format,
    DCT.identifier,
    DCT.type,
    RDFS.label,
    RDFS.comment,
]

for prop in annotation_properties:
    g.add((prop, RDF.type, OWL.AnnotationProperty))

# === 6. Create central instance ===
central = EX["Abstracts_der_58_Katalytikertagung"]
g.add((central, RDF.type, EX["ConferenceAbstractCollection"]))
g.add((central, DCT.title, Literal("Abstracts der 58. Katalytikertagung", lang="de")))


# === Helper: Organization matching ===
def fuzzy_match_score(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def find_affiliated_org(org_string: str, threshold: float = 0.85) -> dict:
    """
    Try to match organization string against known affiliated organizations.

    Returns dict with:
    - 'matched': True if match found
    - 'name': official institution name
    - 'address': full address from list
    - 'confidence': matching confidence score
    """
    org_lower = org_string.lower()

    # Try exact match first
    if org_lower in org_lookup:
        return {
            'matched': True,
            'name': org_lookup[org_lower]['name'],
            'address': org_lookup[org_lower]['address'],
            'confidence': 1.0
        }

    # Try partial/fuzzy matching
    best_match = None
    best_score = 0

    for known_org_lower, org_data in org_lookup.items():
        # Check if one string contains the other
        if org_lower in known_org_lower or known_org_lower in org_lower:
            score = 0.9  # High score for containment
        else:
            score = fuzzy_match_score(org_lower, known_org_lower)

        if score > best_score and score >= threshold:
            best_score = score
            best_match = org_data

    if best_match:
        return {
            'matched': True,
            'name': best_match['name'],
            'address': best_match['address'],
            'confidence': best_score
        }

    return {
        'matched': False,
        'name': org_string,
        'address': None,
        'confidence': 0
    }


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
    Create and add an organization resource.
    - If matched: uses official name and address from the affiliated organizations list.
    - If unmatched: adds organization with only the label (full original string), no location.
    Uses FOAF and schema.org properties to represent the organization structure.
    """
    # Try to match against affiliated organizations
    match_result = find_affiliated_org(org_string)

    if match_result['matched']:
        # Use standardized name and address from affiliated list
        org_name = match_result['name']
        full_address = match_result['address']

        # Log the match for transparency
        print(f"✓ Matched: '{org_string}' -> '{org_name}' (confidence: {match_result['confidence']:.2f})")

        # Parse the standardized address from the list
        parsed = parse_organization(full_address)

        # Add organization with official data from affiliated list
        org_uri = name_to_uri(org_name)
        g.add((abstract_uri, pred, org_uri))
        g.add((org_uri, RDF.type, SCHEMA.Organization))
        g.add((org_uri, RDFS.label, Literal(org_name)))

        # Add address if available (using schema.org PostalAddress)
        if parsed['address']:
            addr_uri = EX[quote(f"{name_to_uri(org_name).split('/')[-1]}_address")]
            g.add((org_uri, SCHEMA.address, addr_uri))
            g.add((addr_uri, RDF.type, SCHEMA.PostalAddress))
            g.add((addr_uri, SCHEMA.streetAddress, Literal(parsed['address'].strip())))

        # Add location if available (using schema.org only)
        if parsed['location']:
            g.add((org_uri, SCHEMA.location, Literal(parsed['location'].strip())))

    else:
        # No match found - add organization with only label (full original string)
        print(f"⚠ No match: '{org_string}' - added with label only (no location)")

        org_uri = name_to_uri(org_string)
        g.add((abstract_uri, pred, org_uri))
        g.add((org_uri, RDF.type, SCHEMA.Organization))
        g.add((org_uri, RDFS.label, Literal(org_string.strip())))


# === 7. Iterate through rows and add RDF triples ===
unmatched_orgs = []

for idx, row in df.iterrows():
    abstract_uri = EX[f"abstract_{idx + 1}"]
    g.add((central, EX.has_abstract, abstract_uri))
    g.add((abstract_uri, RDF.type, EX.Abstract))

    # Track if we have a title to add as rdfs:label later
    abstract_title = None

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

                    # Track unmatched organizations
                    match_result = find_affiliated_org(entry)
                    if not match_result['matched']:
                        unmatched_orgs.append(entry)

                # --- Default behavior ---
                else:
                    obj = interpret_value(entry)
                    g.add((abstract_uri, pred, obj))

                    # Track title for rdfs:label
                    if col_name.lower() == "dct:title":
                        abstract_title = entry

    # Add rdfs:label with the same value as dct:title if title exists
    if abstract_title:
        g.add((abstract_uri, RDFS.label, Literal(abstract_title)))

# === 8. Serialize to Turtle ===
output_file = "abstracts_katalytikertagung_w_affili_w_classes.ttl"
g.serialize(destination=output_file, format="turtle")

print(f"\n✅ RDF graph written to {output_file}")

# === 9. Report unmatched organizations ===
if unmatched_orgs:
    print(f"\n⚠️  Found {len(unmatched_orgs)} unmatched organization(s):")
    for org in set(unmatched_orgs):  # Use set to remove duplicates
        print(f"   - {org}")

    # Save to file for review
    with open("unmatched_organizations.txt", "w", encoding="utf-8") as f:
        f.write("Unmatched Organizations\n")
        f.write("=" * 50 + "\n\n")
        for org in sorted(set(unmatched_orgs)):
            f.write(f"{org}\n")
    print(f"\n📄 Unmatched organizations saved to: unmatched_organizations.txt")
else:
    print("\n✅ All organizations matched successfully!")