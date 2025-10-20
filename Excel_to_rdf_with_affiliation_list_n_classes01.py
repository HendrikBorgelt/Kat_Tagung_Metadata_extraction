import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef, OWL
from rdflib.namespace import DCTERMS, RDFS
import re
from urllib.parse import urlparse, quote
from difflib import SequenceMatcher

# === CONFIGURATION ===
AXIOMATIZE_DCT_RELATION = True

# === 1. Load Excel file ===
excel_path = "metadata_output_for_conversion_20251014_1508.xlsx"
df = pd.read_excel(excel_path)

if 'file_title' in df.columns:
    df = df.drop(columns=['file_title'])

# === 2. Load affiliated organizations list ===
org_list_path = "list_of_affiliated_organisations.txt"
affiliated_orgs = pd.read_csv(org_list_path, sep="\t", encoding="utf-8")
affiliated_orgs.columns = affiliated_orgs.columns.str.strip()

org_lookup = {}
for _, org_row in affiliated_orgs.iterrows():
    institution = str(org_row['INSTITUTION/COMPANY']).strip()
    address = str(org_row['FULL ADDRESS']).strip()
    org_lookup[institution.lower()] = {'name': institution, 'address': address}

# === 3. Namespaces ===
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
# Core classes
g.add((EX.Abstract, RDF.type, OWL.Class))
g.add((FOAF.Agent, RDF.type, OWL.Class))
g.add((SCHEMA.Organization, RDF.type, OWL.Class))

# Object properties for WebVOWL visibility
g.add((DCT.contributor, RDF.type, OWL.ObjectProperty))
g.add((DCT.contributor, RDFS.domain, EX.Abstract))
g.add((DCT.contributor, RDFS.range, FOAF.Agent))

g.add((DCAT.contactPoint, RDF.type, OWL.ObjectProperty))
g.add((DCAT.contactPoint, RDFS.domain, EX.Abstract))
g.add((DCAT.contactPoint, RDFS.range, FOAF.Agent))

g.add((SCHEMA.sourceOrganization, RDF.type, OWL.ObjectProperty))
g.add((SCHEMA.sourceOrganization, RDFS.domain, EX.Abstract))
g.add((SCHEMA.sourceOrganization, RDFS.range, SCHEMA.Organization))

if AXIOMATIZE_DCT_RELATION:
    g.add((DCT.relation, RDF.type, OWL.ObjectProperty))
    g.add((DCT.relation, RDFS.domain, EX.Abstract))
    g.add((DCT.relation, RDFS.range, EX.Abstract))

annotation_properties = [
    DCT.title, DCT.abstract, DCT.subject, DCT.date, DCT.format,
    DCT.identifier, DCT.type, RDFS.label, RDFS.comment
]
for prop in annotation_properties:
    g.add((prop, RDF.type, OWL.AnnotationProperty))

# === 6. Helper functions ===
def fuzzy_match_score(s1, s2):
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

def find_affiliated_org(org_string, threshold=0.85):
    org_lower = org_string.lower()
    if org_lower in org_lookup:
        return {'matched': True, 'name': org_lookup[org_lower]['name'], 'address': org_lookup[org_lower]['address'], 'confidence': 1.0}
    best_match, best_score = None, 0
    for known_org_lower, org_data in org_lookup.items():
        score = 0.9 if org_lower in known_org_lower or known_org_lower in org_lower else fuzzy_match_score(org_lower, known_org_lower)
        if score > best_score and score >= threshold:
            best_match, best_score = org_data, score
    return {'matched': bool(best_match), 'name': best_match['name'] if best_match else org_string, 'address': best_match['address'] if best_match else None, 'confidence': best_score}

def is_valid_uri(uri):
    try:
        result = urlparse(uri)
        return all([result.scheme in ("http", "https"), result.netloc]) and ("," not in uri) and (" " not in uri)
    except Exception:
        return False

def interpret_value(value):
    s = str(value).strip()
    if re.match(r"^(doi:|10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", s, re.IGNORECASE):
        if s.lower().startswith("doi:"):
            s = "https://doi.org/" + s[4:].strip()
        elif re.match(r"^10\.", s):
            s = "https://doi.org/" + s
    if is_valid_uri(s):
        try:
            return URIRef(s)
        except Exception:
            pass
    return Literal(s)

def name_to_uri(name):
    clean = re.sub(r"[^A-Za-z0-9\s._-]", "", name.strip()).replace(".", "").replace(" ", "_")
    return EX[quote(clean)]

def add_foaf_agent(abstract_uri, agent_name):
    agent_uri = name_to_uri(agent_name)
    g.add((agent_uri, RDF.type, OWL.Class))
    g.add((agent_uri, RDFS.subClassOf, FOAF.Agent))
    g.add((agent_uri, RDFS.label, Literal(agent_name.strip())))
    g.add((abstract_uri, DCT.contributor, agent_uri))
    return agent_uri

def add_organization_with_details(abstract_uri, org_string, pred):
    match_result = find_affiliated_org(org_string)
    org_name = match_result['name']
    org_uri = name_to_uri(org_name)
    g.add((org_uri, RDF.type, OWL.Class))
    g.add((org_uri, RDFS.subClassOf, SCHEMA.Organization))
    g.add((org_uri, RDFS.label, Literal(org_name)))
    g.add((abstract_uri, pred, org_uri))

# === 7. Iterate through rows ===
for idx, row in df.iterrows():
    abstract_uri = EX[f"abstract_{idx + 1}"]
    g.add((abstract_uri, RDF.type, OWL.Class))
    g.add((abstract_uri, RDFS.subClassOf, EX.Abstract))

    abstract_title = None

    for col_name, value in row.items():
        if pd.notna(value):
            col_name = col_name.strip()
            prefix, local = (col_name.split(":", 1) + [""])[:2] if ":" in col_name else ("ex", col_name)
            prefix = prefix.lower()
            ns_map = {"dct": DCT, "schema": SCHEMA, "foaf": FOAF, "dcat": DCAT, "ex": EX}
            pred = ns_map.get(prefix, EX)[local]

            entries = [v.strip() for v in str(value).split(",") if v.strip()] if prefix == "foaf" else [v.strip() for v in str(value).split(";") if v.strip()]

            for entry in entries:
                if col_name.lower() == "foaf:agent":
                    add_foaf_agent(abstract_uri, entry)
                elif col_name.lower() == "dcat:contactpoint":
                    agent_uri = add_foaf_agent(abstract_uri, entry)
                    g.add((abstract_uri, DCAT.contactPoint, agent_uri))
                elif col_name.lower().startswith("schema") and "organization" in col_name.lower():
                    add_organization_with_details(abstract_uri, entry, pred)
                else:
                    obj = interpret_value(entry)
                    g.add((abstract_uri, pred, obj))
                    if col_name.lower() == "dct:title":
                        abstract_title = entry

    if abstract_title:
        g.add((abstract_uri, RDFS.label, Literal(abstract_title)))

# === 8. Serialize ===
output_file = "abstracts_katalytikertagung_webvowl.ttl"
g.serialize(destination=output_file, format="turtle")
print(f"✅ WebVOWL-ready RDF written to {output_file}")
