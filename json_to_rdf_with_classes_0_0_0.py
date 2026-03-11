import json
from rdflib import Graph, Namespace, Literal, RDF, URIRef, OWL, XSD, BNode
from rdflib.namespace import DCTERMS, RDFS
import re
from urllib.parse import urlparse, quote
from difflib import SequenceMatcher

# === CONFIGURATION ===
CITATIONS_AS_CLASSES = False  # Set to True to treat citations/references as classes
AXIOMATIZE_DCT_RELATION = True

# === 1. Load JSON file ===
json_path = "metadata_output_20251023_1016_cleaned_affiliations3.json"
with open(json_path, 'r', encoding='utf-8') as f:
    abstracts_data = json.load(f)

print(f"✅ Loaded {len(abstracts_data)} abstracts from JSON")

# === 2. Load affiliated organizations list ===
org_list_path = "list_of_affiliated_organisations.txt"
try:
    import pandas as pd

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

# Instance graph (actual data - pure RDF without OWL)
g_inst = Graph()
g_inst.bind("ex", EX)
g_inst.bind("dct", DCT)
g_inst.bind("rdfs", RDFS)
g_inst.bind("schema", SCHEMA)
g_inst.bind("foaf", FOAF)
g_inst.bind("dcat", DCAT)

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

# Core base classes
g_onto.add((EX.Abstract, RDF.type, OWL.Class))
g_onto.add((EX.Abstract, RDFS.label, Literal("Abstract", lang="en")))
g_onto.add((EX.Abstract, RDFS.comment, Literal("A conference abstract submitted to Katalytikertagung", lang="en")))

g_onto.add((FOAF.Person, RDF.type, OWL.Class))
g_onto.add((FOAF.Person, RDFS.label, Literal("Person", lang="en")))
g_onto.add((FOAF.Person, RDFS.comment, Literal("A person who contributes to abstracts", lang="en")))

g_onto.add((SCHEMA.Organization, RDF.type, OWL.Class))
g_onto.add((SCHEMA.Organization, RDFS.label, Literal("Organization", lang="en")))
g_onto.add(
    (SCHEMA.Organization, RDFS.comment, Literal("An organization affiliated with abstract submissions", lang="en")))

if CITATIONS_AS_CLASSES:
    g_onto.add((EX.Citation, RDF.type, OWL.Class))
    g_onto.add((EX.Citation, RDFS.label, Literal("Citation", lang="en")))
    g_onto.add((EX.Citation, RDFS.comment, Literal("A bibliographic citation or reference", lang="en")))

# Object properties with inverse properties
g_onto.add((EX.hasAuthor, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.hasAuthor, RDFS.label, Literal("has author", lang="en")))
g_onto.add((EX.hasAuthor, RDFS.comment, Literal("Relates an abstract to its author(s)", lang="en")))
g_onto.add((EX.hasAuthor, RDFS.domain, EX.Abstract))
g_onto.add((EX.hasAuthor, RDFS.range, FOAF.Person))

g_onto.add((EX.isAuthorOf, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.isAuthorOf, RDFS.label, Literal("is author of", lang="en")))
g_onto.add((EX.isAuthorOf, RDFS.comment, Literal("Relates a person to abstracts they authored", lang="en")))
g_onto.add((EX.isAuthorOf, RDFS.domain, FOAF.Person))
g_onto.add((EX.isAuthorOf, RDFS.range, EX.Abstract))
g_onto.add((EX.hasAuthor, OWL.inverseOf, EX.isAuthorOf))

# Contributor property removed - only hasAuthor and contactPoint are used

g_onto.add((DCAT.contactPoint, RDF.type, OWL.ObjectProperty))
g_onto.add((DCAT.contactPoint, RDFS.label, Literal("contact point", lang="en")))
g_onto.add((DCAT.contactPoint, RDFS.comment, Literal("Relevant contact information for the abstract", lang="en")))
g_onto.add((DCAT.contactPoint, RDFS.domain, EX.Abstract))
g_onto.add((DCAT.contactPoint, RDFS.range, FOAF.Person))

g_onto.add((EX.isContactFor, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.isContactFor, RDFS.label, Literal("is contact for", lang="en")))
g_onto.add((EX.isContactFor, RDFS.comment, Literal("Relates a person to abstracts they are contact for", lang="en")))
g_onto.add((EX.isContactFor, RDFS.domain, FOAF.Person))
g_onto.add((EX.isContactFor, RDFS.range, EX.Abstract))
g_onto.add((DCAT.contactPoint, OWL.inverseOf, EX.isContactFor))

g_onto.add((EX.hasAffiliation, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.hasAffiliation, RDFS.label, Literal("has affiliation", lang="en")))
g_onto.add((EX.hasAffiliation, RDFS.comment, Literal("Relates a person to affiliated organization(s)", lang="en")))
g_onto.add((EX.hasAffiliation, RDFS.domain, FOAF.Person))
g_onto.add((EX.hasAffiliation, RDFS.range, SCHEMA.Organization))

g_onto.add((EX.isAffiliationOf, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.isAffiliationOf, RDFS.label, Literal("is affiliation of", lang="en")))
g_onto.add(
    (EX.isAffiliationOf, RDFS.comment, Literal("Relates an organization to persons affiliated with it", lang="en")))
g_onto.add((EX.isAffiliationOf, RDFS.domain, SCHEMA.Organization))
g_onto.add((EX.isAffiliationOf, RDFS.range, FOAF.Person))
g_onto.add((EX.hasAffiliation, OWL.inverseOf, EX.isAffiliationOf))

g_onto.add((SCHEMA.sourceOrganization, RDF.type, OWL.ObjectProperty))
g_onto.add((SCHEMA.sourceOrganization, RDFS.label, Literal("source organization", lang="en")))
g_onto.add((SCHEMA.sourceOrganization, RDFS.comment,
            Literal("The organization that is the source of the abstract", lang="en")))
g_onto.add((SCHEMA.sourceOrganization, RDFS.domain, EX.Abstract))
g_onto.add((SCHEMA.sourceOrganization, RDFS.range, SCHEMA.Organization))

g_onto.add((EX.isSourceOf, RDF.type, OWL.ObjectProperty))
g_onto.add((EX.isSourceOf, RDFS.label, Literal("is source of", lang="en")))
g_onto.add(
    (EX.isSourceOf, RDFS.comment, Literal("Relates an organization to abstracts it is the source of", lang="en")))
g_onto.add((EX.isSourceOf, RDFS.domain, SCHEMA.Organization))
g_onto.add((EX.isSourceOf, RDFS.range, EX.Abstract))
g_onto.add((SCHEMA.sourceOrganization, OWL.inverseOf, EX.isSourceOf))

if AXIOMATIZE_DCT_RELATION:
    g_onto.add((DCT.relation, RDF.type, OWL.DatatypeProperty))
    g_onto.add((DCT.relation, RDFS.label, Literal("relation", lang="en")))
    g_onto.add((DCT.relation, RDFS.comment, Literal("A related resource", lang="en")))
    g_onto.add((DCT.relation, RDFS.domain, EX.Abstract))

# Citation/Reference properties
if CITATIONS_AS_CLASSES:
    g_onto.add((EX.hasCitation, RDF.type, OWL.ObjectProperty))
    g_onto.add((EX.hasCitation, RDFS.label, Literal("has citation", lang="en")))
    g_onto.add((EX.hasCitation, RDFS.comment, Literal("Relates an abstract to a citation", lang="en")))
    g_onto.add((EX.hasCitation, RDFS.domain, EX.Abstract))
    g_onto.add((EX.hasCitation, RDFS.range, EX.Citation))

    g_onto.add((EX.isCitationOf, RDF.type, OWL.ObjectProperty))
    g_onto.add((EX.isCitationOf, RDFS.label, Literal("is citation of", lang="en")))
    g_onto.add((EX.isCitationOf, RDFS.comment, Literal("Relates a citation to the abstract it is cited in", lang="en")))
    g_onto.add((EX.isCitationOf, RDFS.domain, EX.Citation))
    g_onto.add((EX.isCitationOf, RDFS.range, EX.Abstract))
    g_onto.add((EX.hasCitation, OWL.inverseOf, EX.isCitationOf))

    g_onto.add((EX.hasReference, RDF.type, OWL.ObjectProperty))
    g_onto.add((EX.hasReference, RDFS.label, Literal("has reference", lang="en")))
    g_onto.add((EX.hasReference, RDFS.comment, Literal("Relates an abstract to a bibliographic reference", lang="en")))
    g_onto.add((EX.hasReference, RDFS.domain, EX.Abstract))
    g_onto.add((EX.hasReference, RDFS.range, EX.Citation))

    g_onto.add((EX.isReferenceOf, RDF.type, OWL.ObjectProperty))
    g_onto.add((EX.isReferenceOf, RDFS.label, Literal("is reference of", lang="en")))
    g_onto.add(
        (EX.isReferenceOf, RDFS.comment, Literal("Relates a reference to the abstract it is referenced in", lang="en")))
    g_onto.add((EX.isReferenceOf, RDFS.domain, EX.Citation))
    g_onto.add((EX.isReferenceOf, RDFS.range, EX.Abstract))
    g_onto.add((EX.hasReference, OWL.inverseOf, EX.isReferenceOf))
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
    RDFS.label, RDFS.comment, OWL.versionInfo, DCT.issued, DCT.language,
    DCT.publisher, DCAT.keyword, DCAT.theme
]
for prop in annotation_properties:
    if (prop, RDF.type, OWL.AnnotationProperty) not in g_onto:
        g_onto.add((prop, RDF.type, OWL.AnnotationProperty))


# === 6. Helper functions ===
def fuzzy_match_score(s1, s2):
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def find_affiliated_org(org_string, threshold=0.85):
    """Find organization in the lookup, returning name and address"""
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


def add_foaf_person_class(person_name):
    """Add person as a class in ontology"""
    person_uri = name_to_uri(person_name)
    if person_uri not in created_author_classes:
        g_onto.add((person_uri, RDF.type, OWL.Class))
        g_onto.add((person_uri, RDFS.subClassOf, FOAF.Person))
        g_onto.add((person_uri, RDFS.label, Literal(person_name.strip())))
        created_author_classes.add(person_uri)
    return person_uri


def add_foaf_person_instance(person_name):
    """Add person as instance in knowledge graph (pure RDF)"""
    if person_name in created_author_instances:
        return created_author_instances[person_name]

    person_uri = name_to_uri(person_name)
    person_class_uri = add_foaf_person_class(person_name)  # Ensure class exists in ontology

    # In instance graph: use base class FOAF.Person as type (not individual class URI)
    g_inst.add((person_uri, RDF.type, FOAF.Person))
    g_inst.add((person_uri, FOAF.name, Literal(person_name.strip())))
    created_author_instances[person_name] = person_uri
    return person_uri


def add_organization_class(org_string):
    """Add organization as a class in ontology (without fuzzy matching)"""
    org_name = org_string.strip()
    org_uri = name_to_uri(org_name)

    if org_uri not in created_org_classes:
        g_onto.add((org_uri, RDF.type, OWL.Class))
        g_onto.add((org_uri, RDFS.subClassOf, SCHEMA.Organization))
        g_onto.add((org_uri, RDFS.label, Literal(org_name)))
        created_org_classes.add(org_uri)
    return org_uri


def add_organization_instance(org_string):
    """Add organization as instance in knowledge graph (pure RDF)"""
    org_name = org_string.strip()

    if org_name in created_org_instances:
        return created_org_instances[org_name]

    org_uri = name_to_uri(org_name)
    org_class_uri = add_organization_class(org_string)  # Ensure class exists in ontology

    # In instance graph: use base class SCHEMA.Organization as type (not individual class URI)
    g_inst.add((org_uri, RDF.type, SCHEMA.Organization))
    g_inst.add((org_uri, SCHEMA.name, Literal(org_name)))

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
    """Add citation as instance in knowledge graph (pure RDF)"""
    if citation_string in created_citation_instances:
        return created_citation_instances[citation_string]

    citation_uri = name_to_uri(citation_string[:100])
    citation_class_uri = add_citation_class(citation_string)

    # In instance graph: use base class EX.Citation as type (not individual class URI)
    g_inst.add((citation_uri, RDF.type, EX.Citation))
    g_inst.add((citation_uri, DCT.bibliographicCitation, Literal(citation_string.strip())))
    created_citation_instances[citation_string] = citation_uri
    return citation_uri


# === 7. Process JSON data ===
for idx, abstract_data in enumerate(abstracts_data):
    # Create abstract class in ontology
    abstract_class_uri = EX[f"Abstract_{idx + 1}"]
    g_onto.add((abstract_class_uri, RDF.type, OWL.Class))
    g_onto.add((abstract_class_uri, RDFS.subClassOf, EX.Abstract))

    # Create abstract instance in knowledge graph (pure RDF)
    abstract_inst_uri = EX[f"abstract_{idx + 1}"]
    g_inst.add((abstract_inst_uri, RDF.type, EX.Abstract))

    abstract_title = None

    # Process all fields except 'authors' and 'dct:relation'
    for key, value in abstract_data.items():
        if key in ['authors', 'dct:relation', 'file_title']:
            continue

        if value and str(value).strip():
            # Parse namespace and property
            if ":" in key:
                prefix, local = key.split(":", 1)
                prefix = prefix.lower()
                ns_map = {"dct": DCT, "schema": SCHEMA, "foaf": FOAF, "dcat": DCAT, "ex": EX}
                pred = ns_map.get(prefix, EX)[local]
            else:
                pred = EX[key]

            # Handle contact point (single string as person)
            if key == "dcat:contactPoint":
                contact_name = str(value).strip()
                person_class_uri = add_foaf_person_class(contact_name)
                person_inst_uri = add_foaf_person_instance(contact_name)

                # Ontology: Add OWL restriction
                add_class_restriction(abstract_class_uri, DCAT.contactPoint, person_class_uri)

                # Instance: link abstract to person (and add inverse)
                g_inst.add((abstract_inst_uri, DCAT.contactPoint, person_inst_uri))
                g_inst.add((person_inst_uri, EX.isContactFor, abstract_inst_uri))

            # Handle keywords (can be empty or semicolon-separated)
            elif key == "dcat:keyword":
                keywords = [k.strip() for k in str(value).split(";") if k.strip()]
                for keyword in keywords:
                    g_inst.add((abstract_inst_uri, pred, Literal(keyword)))
                    add_class_annotation(abstract_class_uri, pred, keyword)

            # Handle other properties
            else:
                obj = interpret_value(value)
                g_inst.add((abstract_inst_uri, pred, obj))
                add_class_annotation(abstract_class_uri, pred, obj)

                if key == "dct:title":
                    abstract_title = str(value)

    # Process authors with their affiliations
    if 'authors' in abstract_data and abstract_data['authors']:
        for author in abstract_data['authors']:
            author_name = author.get('name', '').strip()
            if not author_name:
                continue

            # Create author class and instance
            person_class_uri = add_foaf_person_class(author_name)
            person_inst_uri = add_foaf_person_instance(author_name)

            # Link abstract to author (ontology and instance with inverses)
            add_class_restriction(abstract_class_uri, EX.hasAuthor, person_class_uri)
            g_inst.add((abstract_inst_uri, EX.hasAuthor, person_inst_uri))
            g_inst.add((person_inst_uri, EX.isAuthorOf, abstract_inst_uri))

            # Process author's affiliations
            if 'affiliations' in author and author['affiliations']:
                for affiliation in author['affiliations']:
                    affiliation_str = str(affiliation).strip()
                    if not affiliation_str:
                        continue

                    # Create organization class and instance
                    org_class_uri = add_organization_class(affiliation_str)
                    org_inst_uri = add_organization_instance(affiliation_str)

                    # Link author to organization (ontology and instance with inverses)
                    add_class_restriction(person_class_uri, EX.hasAffiliation, org_class_uri)
                    g_inst.add((person_inst_uri, EX.hasAffiliation, org_inst_uri))
                    g_inst.add((org_inst_uri, EX.isAffiliationOf, person_inst_uri))

    # Process relations (as datatype properties from list)
    if 'dct:relation' in abstract_data and abstract_data['dct:relation']:
        relations = abstract_data['dct:relation']
        if isinstance(relations, list):
            for relation in relations:
                relation_str = str(relation).strip()
                if relation_str:
                    g_inst.add((abstract_inst_uri, DCT.relation, Literal(relation_str)))
        else:
            # Handle case where it's a single string
            relation_str = str(relations).strip()
            if relation_str:
                g_inst.add((abstract_inst_uri, DCT.relation, Literal(relation_str)))

    # Add labels
    if abstract_title:
        g_onto.add((abstract_class_uri, RDFS.label, Literal(abstract_title)))
        g_inst.add((abstract_inst_uri, RDFS.label, Literal(abstract_title)))
    else:
        g_onto.add((abstract_class_uri, RDFS.label, Literal(f"Abstract {idx + 1}")))
        g_inst.add((abstract_inst_uri, RDFS.label, Literal(f"Abstract {idx + 1}")))

# === 8. Serialize both graphs ===
ontology_output = "katalytikertagung_ontology.ttl"
instances_output = "katalytikertagung_instances.ttl"

g_onto.serialize(destination=ontology_output, format="turtle")
g_inst.serialize(destination=instances_output, format="turtle")

print(f"\n✅ OWL Ontology written to {ontology_output}")
print(f"   📊 Ontology triples: {len(g_onto)}")
print(f"   📄 Abstract classes: {len(abstracts_data)}")
print(f"   👤 Person classes: {len(created_author_classes)}")
print(f"   🏢 Organization classes: {len(created_org_classes)}")
if CITATIONS_AS_CLASSES:
    print(f"   📚 Citation classes: {len(created_citation_classes)}")
print(f"   🎯 Ready for WebVOWL visualization!")

print(f"\n✅ Knowledge Graph (instances) written to {instances_output}")
print(f"   📊 Instance triples: {len(g_inst)}")
print(f"   📄 Abstract instances: {len(abstracts_data)}")
print(f"   👤 Person instances: {len(created_author_instances)}")
print(f"   🏢 Organization instances: {len(created_org_instances)}")
if CITATIONS_AS_CLASSES:
    print(f"   📚 Citation instances: {len(created_citation_instances)}")
print(f"   🔍 Ready for SPARQL queries!")
print(f"   ✨ Pure RDF without OWL assertions!")

print(f"\n📌 Configuration:")
print(f"   Citations as classes: {CITATIONS_AS_CLASSES}")
print(f"   DCT.relation axiomatized: {AXIOMATIZE_DCT_RELATION}")
print(f"   Inverse properties: ✅ Implemented for all object properties")