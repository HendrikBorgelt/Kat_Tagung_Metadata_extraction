import os
import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef, OWL, XSD, BNode
from rdflib.namespace import DCTERMS, RDFS
import re
from urllib.parse import urlparse, quote

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
from difflib import SequenceMatcher

# === CONFIGURATION ===
CITATIONS_AS_CLASSES = False  # Set to True to treat citations/references as classes
AXIOMATIZE_DCT_RELATION = True

# === 1. Load Excel file ===
excel_path = os.path.join(_ROOT, "data", "intermediate", "metadata_output_for_conversion_20251014_1508.xlsx")
df = pd.read_excel(excel_path)

if 'file_title' in df.columns:
    df = df.drop(columns=['file_title'])

# === 2. Load affiliated organizations list ===
org_list_path = "list_of_affiliated_organisations.txt"
try:
    affiliated_orgs = pd.read_csv(org_list_path, sep="\t", encoding="utf-8")
    affiliated_orgs.columns = affiliated_orgs.columns.str.strip()

    org_lookup = {}
    for _, org_row in affiliated_orgs.iterrows():
        institution = str(org_row['INSTITUTION/COMPANY']).strip()
        address = str(org_row['FULL ADDRESS']).strip()
        org_lookup[institution.lower()] = {'name': institution, 'address': address}
    print(f"✅ Loaded {len(org_lookup)} affiliated organizations")
except Exception as e:
    print(f"⚠️  Could not load affiliated organizations list: {e}")
    org_lookup = {}

# === 3. Namespaces ===
EX = Namespace("http://example.org/katalytikertagung/")
DCT = DCTERMS
SCHEMA = Namespace("https://schema.org/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
DCAT = Namespace("https://www.w3.org/ns/dcat#")

# === 4. Initialize TWO Graphs ===
# Ontology graph (classes and properties for WebVOWL)
g_onto = Graph()
g_onto.bind("ex", EX)
g_onto.bind("dct", DCT)
g_onto.bind("rdfs", RDFS)
g_onto.bind("schema", SCHEMA)
g_onto.bind("foaf", FOAF)
g_onto.bind("dcat", DCAT)
g_onto.bind("owl", OWL)
g_onto.bind("xsd", XSD)

# Instance graph (actual data)
g_inst = Graph()
g_inst.bind("ex", EX)
g_inst.bind("dct", DCT)
g_inst.bind("rdfs", RDFS)
g_inst.bind("schema", SCHEMA)
g_inst.bind("foaf", FOAF)
g_inst.bind("dcat", DCAT)
g_inst.bind("owl", OWL)
g_inst.bind("xsd", XSD)

# === 5. Define Base Ontology Structure ===
# Ontology declaration with complete metadata
ontology_uri = EX["KatalytikertagungOntology"]
g_onto.add((ontology_uri, RDF.type, OWL.Ontology))
g_onto.add((ontology_uri, RDFS.label, Literal("Katalytikertagung Ontology", lang="en")))
g_onto.add((ontology_uri, DCT.title, Literal("Katalytikertagung Conference Abstracts Ontology", lang="en")))
g_onto.add((ontology_uri, DCT.description, Literal(
    "An ontology for representing abstracts, authors, and organizations from the 58th Katalytikertagung conference.",
    lang="en")))
g_onto.add((ontology_uri, DCT.created, Literal("2025-10-16", datatype=XSD.date)))
g_onto.add((ontology_uri, DCT.creator, Literal("Generated automatically from conference metadata")))
g_onto.add((ontology_uri, OWL.versionInfo, Literal("1.0")))

# Also add metadata to instance graph
g_inst.add((ontology_uri, RDF.type, OWL.Ontology))
g_inst.add((ontology_uri, RDFS.label, Literal("Katalytikertagung Knowledge Graph", lang="en")))
g_inst.add((ontology_uri, DCT.title, Literal("Katalytikertagung Conference Abstracts - Instance Data", lang="en")))
g_inst.add((ontology_uri, DCT.description,
            Literal("Instance data (individuals) for the 58th Katalytikertagung conference abstracts.", lang="en")))
g_inst.add((ontology_uri, DCT.created, Literal("2025-10-16", datatype=XSD.date)))
g_inst.add((ontology_uri, DCT.creator, Literal("Generated automatically from conference metadata")))
g_inst.add((ontology_uri, OWL.versionInfo, Literal("1.0")))

# Core base classes
g_onto.add((EX.Abstract, RDF.type, OWL.Class))
g_onto.add((EX.Abstract, RDFS.label, Literal("Abstract", lang="en")))
g_onto.add((EX.Abstract, RDFS.comment, Literal("A conference abstract submitted to Katalytikertagung", lang="en")))

g_onto.add((FOAF.Agent, RDF.type, OWL.Class))
g_onto.add((FOAF.Agent, RDFS.label, Literal("Agent", lang="en")))
g_onto.add((FOAF.Agent, RDFS.comment, Literal("An agent (person or entity) who contributes to abstracts", lang="en")))

g_onto.add((SCHEMA.Organization, RDF.type, OWL.Class))
g_onto.add((SCHEMA.Organization, RDFS.label, Literal("Organization", lang="en")))
g_onto.add(
    (SCHEMA.Organization, RDFS.comment, Literal("An organization affiliated with abstract submissions", lang="en")))

if CITATIONS_AS_CLASSES:
    g_onto.add((EX.Citation, RDF.type, OWL.Class))
    g_onto.add((EX.Citation, RDFS.label, Literal("Citation", lang="en")))
    g_onto.add((EX.Citation, RDFS.comment, Literal("A bibliographic citation or reference", lang="en")))

# Object properties
g_onto.add((EX.hasAuthor, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.hasAuthor, RDFS.label, Literal("has author", lang="en")))
g_onto.add((EX.hasAuthor, RDFS.comment, Literal("Relates an abstract to its author(s)", lang="en")))
g_onto.add((EX.hasAuthor, RDFS.domain, EX.Abstract))
g_onto.add((EX.hasAuthor, RDFS.range, FOAF.Agent))

g_onto.add((DCT.contributor, RDF.type, OWL.ObjectProperty))
g_onto.add((DCT.contributor, RDFS.label, Literal("contributor", lang="en")))
g_onto.add((DCT.contributor, RDFS.comment,
            Literal("An entity responsible for making contributions to the resource", lang="en")))
g_onto.add((DCT.contributor, RDFS.domain, EX.Abstract))
g_onto.add((DCT.contributor, RDFS.range, FOAF.Agent))

g_onto.add((DCAT.contactPoint, RDF.type, OWL.ObjectProperty))
g_onto.add((DCAT.contactPoint, RDFS.label, Literal("contact point", lang="en")))
g_onto.add((DCAT.contactPoint, RDFS.comment, Literal("Relevant contact information for the abstract", lang="en")))
g_onto.add((DCAT.contactPoint, RDFS.domain, EX.Abstract))
g_onto.add((DCAT.contactPoint, RDFS.range, FOAF.Agent))

g_onto.add((EX.hasAffiliation, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.hasAffiliation, RDFS.label, Literal("has affiliation", lang="en")))
g_onto.add((EX.hasAffiliation, RDFS.comment, Literal("Relates an abstract to affiliated organization(s)", lang="en")))
g_onto.add((EX.hasAffiliation, RDFS.domain, EX.Abstract))
g_onto.add((EX.hasAffiliation, RDFS.range, SCHEMA.Organization))

g_onto.add((SCHEMA.sourceOrganization, RDF.type, OWL.ObjectProperty))
g_onto.add((SCHEMA.sourceOrganization, RDFS.label, Literal("source organization", lang="en")))
g_onto.add((SCHEMA.sourceOrganization, RDFS.comment,
            Literal("The organization that is the source of the abstract", lang="en")))
g_onto.add((SCHEMA.sourceOrganization, RDFS.domain, EX.Abstract))
g_onto.add((SCHEMA.sourceOrganization, RDFS.range, SCHEMA.Organization))

if AXIOMATIZE_DCT_RELATION:
    g_onto.add((DCT.relation, RDF.type, OWL.ObjectProperty))
    g_onto.add((DCT.relation, RDFS.label, Literal("relation", lang="en")))
    g_onto.add((DCT.relation, RDFS.comment, Literal("A related resource", lang="en")))
    g_onto.add((DCT.relation, RDFS.domain, EX.Abstract))
    g_onto.add((DCT.relation, RDFS.range, EX.Abstract))

# Citation/Reference properties
if CITATIONS_AS_CLASSES:
    g_onto.add((EX.hasCitation, RDF.type, OWL.ObjectProperty))
    g_onto.add((EX.hasCitation, RDFS.label, Literal("has citation", lang="en")))
    g_onto.add((EX.hasCitation, RDFS.comment, Literal("Relates an abstract to a citation", lang="en")))
    g_onto.add((EX.hasCitation, RDFS.domain, EX.Abstract))
    g_onto.add((EX.hasCitation, RDFS.range, EX.Citation))

    g_onto.add((EX.hasReference, RDF.type, OWL.ObjectProperty))
    g_onto.add((EX.hasReference, RDFS.label, Literal("has reference", lang="en")))
    g_onto.add((EX.hasReference, RDFS.comment, Literal("Relates an abstract to a bibliographic reference", lang="en")))
    g_onto.add((EX.hasReference, RDFS.domain, EX.Abstract))
    g_onto.add((EX.hasReference, RDFS.range, EX.Citation))
else:
    g_onto.add((EX.citation, RDF.type, OWL.DatatypeProperty))
    g_onto.add((EX.citation, RDFS.label, Literal("citation", lang="en")))
    g_onto.add((EX.citation, RDFS.comment, Literal("A citation as a literal string", lang="en")))
    g_onto.add((EX.citation, RDFS.domain, EX.Abstract))

    g_onto.add((EX.reference, RDF.type, OWL.DatatypeProperty))
    g_onto.add((EX.reference, RDFS.label, Literal("reference", lang="en")))
    g_onto.add((EX.reference, RDFS.comment, Literal("A reference as a literal string", lang="en")))
    g_onto.add((EX.reference, RDFS.domain, EX.Abstract))

# Annotation properties
annotation_properties = [
    DCT.title, DCT.abstract, DCT.subject, DCT.date, DCT.format,
    DCT.identifier, DCT.type, DCT.created, DCT.creator, DCT.description,
    RDFS.label, RDFS.comment, OWL.versionInfo
]
for prop in annotation_properties:
    if (prop, RDF.type, OWL.AnnotationProperty) not in g_onto:
        g_onto.add((prop, RDF.type, OWL.AnnotationProperty))


# === 6. Helper functions ===
def fuzzy_match_score(s1, s2):
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def find_affiliated_org(org_string, threshold=0.85):
    if not org_lookup:
        return {'matched': False, 'name': org_string, 'address': None, 'confidence': 0.0}

    org_lower = org_string.lower()
    if org_lower in org_lookup:
        return {'matched': True, 'name': org_lookup[org_lower]['name'],
                'address': org_lookup[org_lower]['address'], 'confidence': 1.0}

    best_match, best_score = None, 0
    for known_org_lower, org_data in org_lookup.items():
        score = 0.9 if org_lower in known_org_lower or known_org_lower in org_lower else fuzzy_match_score(org_lower,
                                                                                                           known_org_lower)
        if score > best_score and score >= threshold:
            best_match, best_score = org_data, score

    return {'matched': bool(best_match),
            'name': best_match['name'] if best_match else org_string,
            'address': best_match['address'] if best_match else None,
            'confidence': best_score}


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


# Track created classes and instances
created_author_classes = set()
created_org_classes = set()
created_citation_classes = set()
created_author_instances = {}
created_org_instances = {}
created_citation_instances = {}


def add_class_restriction(subject_class_uri, property_uri, filler_class_uri):
    """
    Add OWL restriction: subject_class rdfs:subClassOf [owl:Restriction; owl:onProperty property; owl:someValuesFrom filler]
    This creates a class-level axiom that WebVOWL can visualize as an edge.
    """
    restriction = BNode()
    g_onto.add((restriction, RDF.type, OWL.Restriction))
    g_onto.add((restriction, OWL.onProperty, property_uri))
    g_onto.add((restriction, OWL.someValuesFrom, filler_class_uri))
    g_onto.add((subject_class_uri, RDFS.subClassOf, restriction))


def add_class_annotation(subject_class_uri, property_uri, value):
    """
    Add an annotation property to a class in the ontology.
    This adds metadata directly to the class without creating edges.
    """
    # Ensure the property is declared as an annotation property
    if (property_uri, RDF.type, OWL.AnnotationProperty) not in g_onto:
        g_onto.add((property_uri, RDF.type, OWL.AnnotationProperty))

    # Add the annotation to the class
    if isinstance(value, URIRef):
        g_onto.add((subject_class_uri, property_uri, value))
    else:
        g_onto.add((subject_class_uri, property_uri, Literal(str(value))))


def add_foaf_agent_class(agent_name):
    """Add agent as a class in ontology"""
    agent_uri = name_to_uri(agent_name)
    if agent_uri not in created_author_classes:
        g_onto.add((agent_uri, RDF.type, OWL.Class))
        g_onto.add((agent_uri, RDFS.subClassOf, FOAF.Agent))
        g_onto.add((agent_uri, RDFS.label, Literal(agent_name.strip())))
        created_author_classes.add(agent_uri)
    return agent_uri


def add_foaf_agent_instance(agent_name):
    """Add agent as instance in knowledge graph"""
    if agent_name in created_author_instances:
        return created_author_instances[agent_name]

    agent_uri = name_to_uri(agent_name)
    agent_class_uri = add_foaf_agent_class(agent_name)  # Ensure class exists
    g_inst.add((agent_uri, RDF.type, agent_class_uri))
    g_inst.add((agent_uri, FOAF.name, Literal(agent_name.strip())))
    created_author_instances[agent_name] = agent_uri
    return agent_uri


def add_organization_class(org_string):
    """Add organization as a class in ontology"""
    match_result = find_affiliated_org(org_string)
    org_name = match_result['name']
    org_uri = name_to_uri(org_name)

    if org_uri not in created_org_classes:
        g_onto.add((org_uri, RDF.type, OWL.Class))
        g_onto.add((org_uri, RDFS.subClassOf, SCHEMA.Organization))
        g_onto.add((org_uri, RDFS.label, Literal(org_name)))
        created_org_classes.add(org_uri)
    return org_uri, match_result


def add_organization_instance(org_string):
    """Add organization as instance in knowledge graph"""
    match_result = find_affiliated_org(org_string)
    org_name = match_result['name']

    if org_name in created_org_instances:
        return created_org_instances[org_name]

    org_uri = name_to_uri(org_name)
    org_class_uri, _ = add_organization_class(org_string)  # Ensure class exists
    g_inst.add((org_uri, RDF.type, org_class_uri))
    g_inst.add((org_uri, SCHEMA.name, Literal(org_name)))

    if match_result['address']:
        g_inst.add((org_uri, SCHEMA.address, Literal(match_result['address'])))

    created_org_instances[org_name] = org_uri
    return org_uri


def add_citation_class(citation_string):
    """Add citation as a class in ontology"""
    citation_uri = name_to_uri(citation_string[:100])

    if citation_uri not in created_citation_classes:
        g_onto.add((citation_uri, RDF.type, OWL.Class))
        g_onto.add((citation_uri, RDFS.subClassOf, EX.Citation))
        g_onto.add((citation_uri, RDFS.label, Literal(citation_string[:200])))
        created_citation_classes.add(citation_uri)
    return citation_uri


def add_citation_instance(citation_string):
    """Add citation as instance in knowledge graph"""
    if citation_string in created_citation_instances:
        return created_citation_instances[citation_string]

    citation_uri = name_to_uri(citation_string[:100])
    citation_class_uri = add_citation_class(citation_string)
    g_inst.add((citation_uri, RDF.type, citation_class_uri))
    g_inst.add((citation_uri, DCT.bibliographicCitation, Literal(citation_string.strip())))
    created_citation_instances[citation_string] = citation_uri
    return citation_uri


# === 7. Iterate through rows ===
for idx, row in df.iterrows():
    # Create abstract class in ontology
    abstract_class_uri = EX[f"Abstract_{idx + 1}"]
    g_onto.add((abstract_class_uri, RDF.type, OWL.Class))
    g_onto.add((abstract_class_uri, RDFS.subClassOf, EX.Abstract))

    # Create abstract instance in knowledge graph
    abstract_inst_uri = EX[f"abstract_{idx + 1}"]
    g_inst.add((abstract_inst_uri, RDF.type, abstract_class_uri))

    abstract_title = None

    for col_name, value in row.items():
        if pd.notna(value):
            col_name = col_name.strip()

            # Determine if this is a citation/reference column
            is_citation_col = any(keyword in col_name.lower() for keyword in ['citation', 'reference', 'bibliographic'])

            # Parse namespace and predicate
            prefix, local = (col_name.split(":", 1) + [""])[:2] if ":" in col_name else ("ex", col_name)
            prefix = prefix.lower()
            ns_map = {"dct": DCT, "schema": SCHEMA, "foaf": FOAF, "dcat": DCAT, "ex": EX}
            pred = ns_map.get(prefix, EX)[local]

            # Split entries
            entries = [v.strip() for v in str(value).split(",") if v.strip()] if prefix == "foaf" else [v.strip() for v
                                                                                                        in
                                                                                                        str(value).split(
                                                                                                            ";") if
                                                                                                        v.strip()]

            for entry in entries:
                # Handle authors (FOAF:Agent)
                if col_name.lower() == "foaf:agent":
                    agent_class_uri = add_foaf_agent_class(entry)
                    agent_inst_uri = add_foaf_agent_instance(entry)
                    # Ontology: Add OWL restriction (class-level axiom)
                    add_class_restriction(abstract_class_uri, EX.hasAuthor, agent_class_uri)
                    # Instance: link abstract instance to agent instance
                    g_inst.add((abstract_inst_uri, EX.hasAuthor, agent_inst_uri))
                    g_inst.add((abstract_inst_uri, DCT.contributor, agent_inst_uri))

                # Handle contact points
                elif col_name.lower() == "dcat:contactpoint":
                    agent_class_uri = add_foaf_agent_class(entry)
                    agent_inst_uri = add_foaf_agent_instance(entry)
                    # Ontology: Add OWL restriction (class-level axiom)
                    add_class_restriction(abstract_class_uri, DCAT.contactPoint, agent_class_uri)
                    # Instance: link abstract instance to agent instance
                    g_inst.add((abstract_inst_uri, DCAT.contactPoint, agent_inst_uri))

                # Handle organizations
                elif col_name.lower().startswith("schema") and "organization" in col_name.lower():
                    org_class_uri, _ = add_organization_class(entry)
                    org_inst_uri = add_organization_instance(entry)
                    # Ontology: Add OWL restriction (class-level axiom)
                    add_class_restriction(abstract_class_uri, EX.hasAffiliation, org_class_uri)
                    # Instance: link abstract instance to org instance
                    g_inst.add((abstract_inst_uri, EX.hasAffiliation, org_inst_uri))
                    g_inst.add((abstract_inst_uri, pred, org_inst_uri))

                # Handle citations/references
                elif is_citation_col and CITATIONS_AS_CLASSES:
                    citation_class_uri = add_citation_class(entry)
                    citation_inst_uri = add_citation_instance(entry)
                    # Determine property
                    citation_prop = EX.hasCitation if 'citation' in col_name.lower() else EX.hasReference
                    # Ontology: Add OWL restriction (class-level axiom)
                    add_class_restriction(abstract_class_uri, citation_prop, citation_class_uri)
                    # Instance: link abstract instance to citation instance
                    g_inst.add((abstract_inst_uri, citation_prop, citation_inst_uri))

                elif is_citation_col and not CITATIONS_AS_CLASSES:
                    # Add as datatype property (instance only)
                    citation_prop = EX.citation if 'citation' in col_name.lower() else EX.reference
                    g_inst.add((abstract_inst_uri, citation_prop, Literal(entry)))

                # Handle other properties
                else:
                    obj = interpret_value(entry)
                    # Add to instance graph
                    g_inst.add((abstract_inst_uri, pred, obj))
                    # Add as annotation to the class in ontology
                    add_class_annotation(abstract_class_uri, pred, obj)

                    if col_name.lower() == "dct:title":
                        abstract_title = entry

    # Add labels
    if abstract_title:
        g_onto.add((abstract_class_uri, RDFS.label, Literal(abstract_title)))
        g_inst.add((abstract_inst_uri, RDFS.label, Literal(abstract_title)))
    else:
        g_onto.add((abstract_class_uri, RDFS.label, Literal(f"Abstract {idx + 1}")))
        g_inst.add((abstract_inst_uri, RDFS.label, Literal(f"Abstract {idx + 1}")))

# === 8. Serialize both graphs ===
ontology_output = os.path.join(_ROOT, "data", "rdf", "katalytikertagung_ontology.ttl")
instances_output = os.path.join(_ROOT, "data", "rdf", "katalytikertagung_instances.ttl")

g_onto.serialize(destination=ontology_output, format="turtle")
g_inst.serialize(destination=instances_output, format="turtle")

print(f"\n✅ OWL Ontology written to {ontology_output}")
print(f"   📊 Ontology triples: {len(g_onto)}")
print(f"   📝 Abstract classes: {len(df)}")
print(f"   👤 Author classes: {len(created_author_classes)}")
print(f"   🏢 Organization classes: {len(created_org_classes)}")
if CITATIONS_AS_CLASSES:
    print(f"   📚 Citation classes: {len(created_citation_classes)}")
print(f"   🎯 Ready for WebVOWL visualization!")

print(f"\n✅ Knowledge Graph (instances) written to {instances_output}")
print(f"   📊 Instance triples: {len(g_inst)}")
print(f"   📝 Abstract instances: {len(df)}")
print(f"   👤 Author instances: {len(created_author_instances)}")
print(f"   🏢 Organization instances: {len(created_org_instances)}")
if CITATIONS_AS_CLASSES:
    print(f"   📚 Citation instances: {len(created_citation_instances)}")
print(f"   🔍 Ready for SPARQL queries!")

print(f"\n📌 Configuration:")
print(f"   Citations as classes: {CITATIONS_AS_CLASSES}")
print(f"   DCT.relation axiomatized: {AXIOMATIZE_DCT_RELATION}")