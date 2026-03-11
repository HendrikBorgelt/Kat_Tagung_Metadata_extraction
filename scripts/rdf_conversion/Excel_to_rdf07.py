import os
import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef, BNode, OWL, XSD
from rdflib.namespace import DCTERMS, RDFS
import re
from urllib.parse import urlparse, quote

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# === 1. Load Excel file ===
excel_path = os.path.join(_ROOT, "data", "intermediate", "metadata_output_for_conversion_20251014_1508.xlsx")
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

# === 5. Define Base Classes (as classes in ontology) ===
g.add((EX["ConferenceAbstractCollection"], RDF.type, OWL.Class))
g.add((EX["Abstract"], RDF.type, OWL.Class))
g.add((FOAF.Agent, RDF.type, OWL.Class))
g.add((SCHEMA.Organization, RDF.type, OWL.Class))
g.add((SCHEMA.PostalAddress, RDF.type, OWL.Class))

# === 6. Define some common properties (declarations can expand during runtime) ===
# We'll declare typed properties on first use via declare_property()

# === 7. Central collection class ===
central = EX["Abstracts_der_58_Katalytikertagung"]
g.add((central, RDF.type, OWL.Class))
g.add((central, RDFS.subClassOf, EX["ConferenceAbstractCollection"]))
g.add((central, RDFS.label, Literal("Abstracts der 58. Katalytikertagung", lang="de")))

# === Helper: URI failsafe ===
def is_valid_uri(uri: str) -> bool:
    try:
        result = urlparse(uri)
        return all([result.scheme in ("http", "https"), result.netloc]) and ("," not in uri) and (" " not in uri)
    except Exception:
        return False

# Reuse DOI/URI detection/normalization
def interpret_value_as_uri_or_literal(value):
    s = str(value).strip()
    # Normalize DOI
    if re.match(r"^(doi:|10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", s, re.IGNORECASE):
        if s.lower().startswith("doi:"):
            s = "https://doi.org/" + s[4:].strip()
        else:
            s = "https://doi.org/" + s
    if is_valid_uri(s):
        try:
            return URIRef(s)
        except Exception:
            pass
    return Literal(s)

def name_to_uri(name: str) -> URIRef:
    clean = name.strip()
    clean = re.sub(r"[^A-Za-z0-9\s._-]", "", clean)
    clean = clean.replace(".", "").replace(" ", "_")
    return EX[quote(clean)]

# === Create class (if not present) helper ===
def ensure_class(uri: URIRef, label: str = None, superclass: URIRef = None):
    if (uri, RDF.type, OWL.Class) not in g:
        g.add((uri, RDF.type, OWL.Class))
    if superclass is not None:
        if (uri, RDFS.subClassOf, superclass) not in g:
            g.add((uri, RDFS.subClassOf, superclass))
    if label:
        if (uri, RDFS.label, Literal(label.strip())) not in g:
            g.add((uri, RDFS.label, Literal(label.strip())))

# === Declare property helper ===
def declare_property(pred: URIRef, is_object_property: bool):
    """Declare a property as ObjectProperty or DatatypeProperty if not already declared."""
    if (pred, RDF.type, OWL.ObjectProperty) in g or (pred, RDF.type, OWL.DatatypeProperty) in g:
        return
    if is_object_property:
        g.add((pred, RDF.type, OWL.ObjectProperty))
    else:
        g.add((pred, RDF.type, OWL.DatatypeProperty))
    local_name = str(pred).split('/')[-1].split('#')[-1]
    g.add((pred, RDFS.label, Literal(local_name.replace('_', ' '))))

# === Create OWL restriction and attach as rdfs:subClassOf to a class ===
def add_class_restriction(subject_class: URIRef, property_uri: URIRef, filler):
    """
    subject_class rdfs:subClassOf _:b .
    _:b a owl:Restriction .
    _:b owl:onProperty property_uri .
    _:b owl:someValuesFrom filler   (if filler is URIRef)
    OR
    _:b owl:hasValue "literal"       (if filler is Literal)
    """
    # determine whether filler is class (URIRef) or literal
    b = BNode()
    g.add((b, RDF.type, OWL.Restriction))
    g.add((b, OWL.onProperty, property_uri))

    if isinstance(filler, URIRef):
        g.add((b, OWL.someValuesFrom, filler))
        declare_property(property_uri, True)
    else:
        # literal: use hasValue (this creates a restriction that the property has that value)
        g.add((b, OWL.hasValue, filler))
        declare_property(property_uri, False)

    # attach restriction to subject_class as a superclass
    g.add((subject_class, RDFS.subClassOf, b))
    return b

# === Special handlers for FOAF Agent and Organizations as classes ===
def add_foaf_agent_class(abstract_class_uri, agent_name: str, property_uri):
    agent_uri = name_to_uri(agent_name)
    ensure_class(agent_uri, label=agent_name.strip(), superclass=FOAF.Agent)
    # add restriction: Abstract_{n} subClassOf (property some AgentClass)
    add_class_restriction(abstract_class_uri, property_uri, agent_uri)
    return agent_uri

def parse_organization(org_string: str) -> dict:
    parts = [p.strip() for p in org_string.split(",")]
    result = {'name': org_string.strip(), 'address': None, 'location': None}
    if len(parts) == 1:
        return result
    if len(parts) == 2:
        result['name'] = parts[0]
        result['location'] = parts[1]
        return result
    # try to find a part that looks like an address (contains digits)
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

def add_organization_class_with_details(abstract_class_uri, org_string: str, property_uri):
    parsed = parse_organization(org_string)
    org_uri = name_to_uri(parsed['name'])
    ensure_class(org_uri, label=parsed['name'], superclass=SCHEMA.Organization)
    # link via restriction: Abstract subClassOf (property some OrgClass)
    add_class_restriction(abstract_class_uri, property_uri, org_uri)

    # address as PostalAddress subclass (class), link org_uri -> schema:address some PostalAddress via class restriction
    if parsed['address']:
        addr_local = name_to_uri(parsed['name']).split('/')[-1] + "_address"
        addr_uri = EX[addr_local]
        ensure_class(addr_uri, label=f"{parsed['name']} address", superclass=SCHEMA.PostalAddress)
        # also add streetAddress as a data property value on the address class using a restriction:
        # addr_uri rdfs:subClassOf [ a owl:Restriction ; owl:onProperty schema:streetAddress ; owl:hasValue "addr literal" ]
        add_class_restriction(addr_uri, SCHEMA.streetAddress, Literal(parsed['address'].strip()))
        # now assert org_uri subClassOf (schema:address some addr_uri)
        add_class_restriction(org_uri, SCHEMA.address, addr_uri)

    if parsed['location']:
        # store location as a data-value restriction on org class (hasValue) or someValuesFrom with literal
        # We'll use hasValue on schema:location
        add_class_restriction(org_uri, SCHEMA.location, Literal(parsed['location'].strip()))

# === 8. Iterate through rows and create OWL classes & restrictions ===
for idx, row in df.iterrows():
    abstract_class_uri = EX[f"Abstract_{idx + 1}"]
    ensure_class(abstract_class_uri, label=f"Abstract {idx + 1}", superclass=EX.Abstract)

    # Link abstract to central collection via a restriction: central subClassOf (ex:has_abstract some Abstract_n)
    # (This creates central rdfs:subClassOf _:b . _:b owl:onProperty ex:has_abstract ; _:b owl:someValuesFrom Abstract_n)
    add_class_restriction(central, EX.has_abstract, abstract_class_uri)

    for col_name, value in row.items():
        if pd.notna(value):
            col_name = col_name.strip()

            # choose predicate NS
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

            # splitting rules: authors often comma-separated, others semicolon
            entries = None
            if ":" in col_name and col_name.lower().startswith("foaf:"):
                entries = [v.strip() for v in str(value).split(",") if v.strip()]
            else:
                entries = [v.strip() for v in str(value).split(";") if v.strip()]

            for entry in entries:
                # FOAF Agent -> class + restriction using dct:contributor
                if col_name.lower() == "foaf:agent":
                    add_foaf_agent_class(abstract_class_uri, entry, DCT.contributor)

                # DCAT contactPoint -> FOAF agent class + restriction using dcat:contactPoint
                elif col_name.lower() == "dcat:contactpoint":
                    add_foaf_agent_class(abstract_class_uri, entry, DCAT.contactPoint)

                # Organization with details -> class + nested address class + restrictions
                elif col_name.lower().startswith("schema") and "organization" in col_name.lower():
                    add_organization_class_with_details(abstract_class_uri, entry, pred)

                else:
                    # determine if entry is URI or literal
                    obj = interpret_value_as_uri_or_literal(entry)

                    # If object is URI (class-like), create class and then a restriction someValuesFrom
                    if isinstance(obj, URIRef):
                        # create class for the filler if it doesn't exist (we'll treat filler as class)
                        ensure_class(obj, label=str(entry))
                        add_class_restriction(abstract_class_uri, pred, obj)
                    else:
                        # literal: create a hasValue restriction on the abstract class
                        add_class_restriction(abstract_class_uri, pred, obj)

# === 9. Serialize to Turtle ===
output_file = os.path.join(_ROOT, "data", "rdf", "abstracts_katalytikertagung_owl_classes.ttl")
g.serialize(destination=output_file, format="turtle")

print(f"✅ OWL ontology written to {output_file}")
print(f"📊 Total triples: {len(g)}")
print(f"🎯 Ready for WebVOWL visualization!")
