import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef, OWL, XSD
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
g.bind("owl", OWL)
g.bind("xsd", XSD)

# === 4. Define OWL Ontology ===
ontology_uri = EX["KatalytikertagungOntology"]
g.add((ontology_uri, RDF.type, OWL.Ontology))
g.add((ontology_uri, RDFS.label, Literal("Katalytikertagung Ontology")))

# === 5. Define Base Classes ===
g.add((EX["ConferenceAbstractCollection"], RDF.type, OWL.Class))
g.add((EX["ConferenceAbstractCollection"], RDFS.label, Literal("Conference Abstract Collection")))

g.add((EX["Abstract"], RDF.type, OWL.Class))
g.add((EX["Abstract"], RDFS.label, Literal("Abstract")))

g.add((FOAF.Agent, RDF.type, OWL.Class))
g.add((FOAF.Agent, RDFS.label, Literal("Agent")))

g.add((SCHEMA.Organization, RDF.type, OWL.Class))
g.add((SCHEMA.Organization, RDFS.label, Literal("Organization")))

g.add((SCHEMA.PostalAddress, RDF.type, OWL.Class))
g.add((SCHEMA.PostalAddress, RDFS.label, Literal("Postal Address")))

# === 6. Define Object Properties ===
# Define has_abstract as object property
g.add((EX.has_abstract, RDF.type, OWL.ObjectProperty))
g.add((EX.has_abstract, RDFS.label, Literal("has abstract")))
g.add((EX.has_abstract, RDFS.domain, EX["ConferenceAbstractCollection"]))
g.add((EX.has_abstract, RDFS.range, EX["Abstract"]))

# Define contributor as object property
g.add((DCT.contributor, RDF.type, OWL.ObjectProperty))
g.add((DCT.contributor, RDFS.label, Literal("contributor")))
g.add((DCT.contributor, RDFS.domain, EX["Abstract"]))
g.add((DCT.contributor, RDFS.range, FOAF.Agent))

# Define contactPoint as object property
g.add((DCAT.contactPoint, RDF.type, OWL.ObjectProperty))
g.add((DCAT.contactPoint, RDFS.label, Literal("contact point")))
g.add((DCAT.contactPoint, RDFS.domain, EX["Abstract"]))
g.add((DCAT.contactPoint, RDFS.range, FOAF.Agent))

# Define organization-related object properties
g.add((SCHEMA.address, RDF.type, OWL.ObjectProperty))
g.add((SCHEMA.address, RDFS.label, Literal("address")))
g.add((SCHEMA.address, RDFS.domain, SCHEMA.Organization))
g.add((SCHEMA.address, RDFS.range, SCHEMA.PostalAddress))

g.add((FOAF.based_near, RDF.type, OWL.ObjectProperty))
g.add((FOAF.based_near, RDFS.label, Literal("based near")))

# === 7. Define Data Properties ===
# Common data properties
g.add((DCT.title, RDF.type, OWL.DatatypeProperty))
g.add((DCT.title, RDFS.label, Literal("title")))

g.add((DCT.description, RDF.type, OWL.DatatypeProperty))
g.add((DCT.description, RDFS.label, Literal("description")))

g.add((RDFS.label, RDF.type, OWL.DatatypeProperty))

g.add((SCHEMA.streetAddress, RDF.type, OWL.DatatypeProperty))
g.add((SCHEMA.streetAddress, RDFS.label, Literal("street address")))
g.add((SCHEMA.streetAddress, RDFS.domain, SCHEMA.PostalAddress))

g.add((SCHEMA.location, RDF.type, OWL.DatatypeProperty))
g.add((SCHEMA.location, RDFS.label, Literal("location")))

# Create central collection class
central = EX["Abstracts_der_58_Katalytikertagung"]
g.add((central, RDF.type, OWL.Class))
g.add((central, RDFS.subClassOf, EX["ConferenceAbstractCollection"]))
g.add((central, RDFS.label, Literal("Abstracts der 58. Katalytikertagung", lang="de")))


# === Helper: URI failsafe ===
def is_valid_uri(uri: str) -> bool:
    """Check if string looks like a valid absolute URI (failsafe)."""
    try:
        result = urlparse(uri)
        return all([result.scheme in ("http", "https"), result.netloc]) and ("," not in uri) and (" " not in uri)
    except Exception:
        return False


def is_object_property_value(value, pred) -> bool:
    """Determine if a value should be treated as an object property (URI) or datatype property (literal)."""
    s = str(value).strip()

    # Check if it's a URI or DOI
    if re.match(r"^(doi:|10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", s, re.IGNORECASE):
        return True
    if is_valid_uri(s):
        return True

    return False


def interpret_value_as_class_or_literal(value, pred):
    """
    Return URIRef (for object properties) or Literal (for datatype properties).
    If it's a URI/DOI, return URIRef. Otherwise return Literal.
    """
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

    # Fallback: treat as literal
    return Literal(s)


def name_to_uri(name: str) -> URIRef:
    """Generate a readable and URI-safe identifier for a name."""
    clean = name.strip()
    clean = re.sub(r"[^A-Za-z0-9\s._-]", "", clean)
    clean = clean.replace(".", "").replace(" ", "_")
    return EX[quote(clean)]


def add_foaf_agent_class(abstract_class_uri, agent_name: str, pred):
    """Create and add a FOAF Agent class with label."""
    agent_uri = name_to_uri(agent_name)

    # Add the agent class if not already present
    if (agent_uri, RDF.type, OWL.Class) not in g:
        g.add((agent_uri, RDF.type, OWL.Class))
        g.add((agent_uri, RDFS.subClassOf, FOAF.Agent))
        g.add((agent_uri, RDFS.label, Literal(agent_name.strip())))

    # Link abstract to agent via object property
    g.add((abstract_class_uri, pred, agent_uri))

    return agent_uri


def parse_organization(org_string: str) -> dict:
    """
    Parse organization string into components (name, address, location).
    """
    parts = [p.strip() for p in org_string.split(",")]

    result = {
        'name': org_string.strip(),
        'address': None,
        'location': None
    }

    if len(parts) == 1:
        return result

    if len(parts) == 2:
        result['name'] = parts[0]
        result['location'] = parts[1]
        return result

    has_digit_index = None
    for i, part in enumerate(parts):
        if any(char.isdigit() for char in part):
            has_digit_index = i
            break

    if has_digit_index is not None and has_digit_index > 0:
        result['name'] = ", ".join(parts[:has_digit_index])
        result['address'] = parts[has_digit_index]
        result['location'] = ", ".join(parts[has_digit_index + 1:]) if has_digit_index + 1 < len(parts) else None
    else:
        result['name'] = parts[0]
        result['location'] = ", ".join(parts[1:])

    return result


def add_organization_class_with_details(abstract_class_uri, org_string: str, pred):
    """
    Create and add an organization class with address and location.
    Uses object properties for structural relationships and datatype properties for literals.
    """
    parsed = parse_organization(org_string)

    org_uri = name_to_uri(parsed['name'])

    # Add organization class if not already present
    if (org_uri, RDF.type, OWL.Class) not in g:
        g.add((org_uri, RDF.type, OWL.Class))
        g.add((org_uri, RDFS.subClassOf, SCHEMA.Organization))
        g.add((org_uri, RDFS.label, Literal(parsed['name'].strip())))

    # Link abstract to organization via object property
    g.add((abstract_class_uri, pred, org_uri))

    # Add address as a separate class linked via object property
    if parsed['address']:
        addr_uri = EX[quote(f"{name_to_uri(parsed['name']).split('/')[-1]}_address")]

        if (addr_uri, RDF.type, OWL.Class) not in g:
            g.add((addr_uri, RDF.type, OWL.Class))
            g.add((addr_uri, RDFS.subClassOf, SCHEMA.PostalAddress))
            g.add((addr_uri, SCHEMA.streetAddress, Literal(parsed['address'].strip())))

        # Link organization to address via object property
        g.add((org_uri, SCHEMA.address, addr_uri))

    # Add location as datatype property
    if parsed['location']:
        g.add((org_uri, SCHEMA.location, Literal(parsed['location'].strip())))


def declare_property(pred, value):
    """Declare a property as ObjectProperty or DatatypeProperty if not already declared."""
    # Skip if already declared
    if (pred, RDF.type, OWL.ObjectProperty) in g or (pred, RDF.type, OWL.DatatypeProperty) in g:
        return

    # Determine property type based on value
    if isinstance(value, URIRef):
        g.add((pred, RDF.type, OWL.ObjectProperty))
    else:
        g.add((pred, RDF.type, OWL.DatatypeProperty))

    # Add a label based on the local name
    local_name = pred.split('/')[-1].split('#')[-1]
    label = local_name.replace('_', ' ')
    g.add((pred, RDFS.label, Literal(label)))


# === 8. Iterate through rows and create OWL classes ===
for idx, row in df.iterrows():
    abstract_class_uri = EX[f"Abstract_{idx + 1}"]
    g.add((abstract_class_uri, RDF.type, OWL.Class))
    g.add((abstract_class_uri, RDFS.subClassOf, EX.Abstract))

    # Link to central collection class via object property
    g.add((central, EX.has_abstract, abstract_class_uri))

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
                entries = [v.strip() for v in str(value).split(",") if v.strip()]
            else:
                entries = [v.strip() for v in str(value).split(";") if v.strip()]

            for entry in entries:
                # --- Handle FOAF Agents (authors/contributors) ---
                if col_name.lower() == "foaf:agent":
                    add_foaf_agent_class(abstract_class_uri, entry, DCT.contributor)

                # --- Handle DCAT Contact Point ---
                elif col_name.lower() == "dcat:contactpoint":
                    add_foaf_agent_class(abstract_class_uri, entry, DCAT.contactPoint)

                # --- Handle Organizations ---
                elif col_name.lower().startswith("schema") and "organization" in col_name.lower():
                    add_organization_class_with_details(abstract_class_uri, entry, pred)

                # --- Default behavior: determine property type and add triple ---
                else:
                    obj = interpret_value_as_class_or_literal(entry, pred)

                    # Declare property type
                    declare_property(pred, obj)

                    # Add triple
                    g.add((abstract_class_uri, pred, obj))

# === 9. Serialize to Turtle ===
output_file = "abstracts_katalytikertagung_owl_classes.ttl"
g.serialize(destination=output_file, format="turtle")

print(f"✅ OWL ontology written to {output_file}")
print(f"📊 Total triples: {len(g)}")
print(f"🎯 Ready for WebVOWL visualization!")