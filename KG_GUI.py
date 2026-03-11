import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from rdflib import Graph, Namespace, RDF, RDFS, FOAF
from rdflib.namespace import DCTERMS
import json
import os
from difflib import SequenceMatcher
from collections import defaultdict

# === Namespaces ===
EX = Namespace("http://example.org/katalytikertagung/")
DCT = DCTERMS
SCHEMA = Namespace("https://schema.org/")
DCAT = Namespace("https://www.w3.org/ns/dcat#")


# === Load RDF Graph ===
def load_graph(file_path):
    """Load the RDF instance graph"""
    g = Graph()
    g.parse(file_path, format="turtle")
    return g


# === Fuzzy Search Functions ===
def fuzzy_match_score(s1, s2):
    """Calculate similarity score between two strings"""
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def search_persons(g, query, threshold=0.3):
    """Search for persons with fuzzy matching"""
    results = []
    query_lower = query.lower()

    for person_uri in g.subjects(RDF.type, FOAF.Person):
        name = str(g.value(person_uri, FOAF.name, default=""))
        if name:
            score = fuzzy_match_score(query_lower, name.lower())
            if score >= threshold or query_lower in name.lower():
                results.append((person_uri, name, score))

    # Sort by score descending
    results.sort(key=lambda x: x[2], reverse=True)
    return [(uri, name) for uri, name, score in results[:10]]  # Top 10 matches


def search_abstracts(g, query, threshold=0.3):
    """Search for abstracts with fuzzy matching"""
    results = []
    query_lower = query.lower()

    for abstract_uri in g.subjects(RDF.type, EX.Abstract):
        title = str(g.value(abstract_uri, DCT.title, default=""))
        label = str(g.value(abstract_uri, RDFS.label, default=""))
        search_text = f"{title} {label}".lower()

        if title or label:
            score = fuzzy_match_score(query_lower, search_text)
            display_name = title or label or str(abstract_uri)
            if score >= threshold or query_lower in search_text:
                results.append((abstract_uri, display_name, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return [(uri, name) for uri, name, score in results[:10]]


def search_organizations(g, query, threshold=0.3):
    """Search for organizations with fuzzy matching"""
    results = []
    query_lower = query.lower()

    for org_uri in g.subjects(RDF.type, SCHEMA.Organization):
        name = str(g.value(org_uri, SCHEMA.name, default=""))
        label = str(g.value(org_uri, RDFS.label, default=""))
        search_text = f"{name} {label}".lower()

        if name or label:
            score = fuzzy_match_score(query_lower, search_text)
            display_name = name or label or str(org_uri)
            if score >= threshold or query_lower in search_text:
                results.append((org_uri, display_name, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return [(uri, name) for uri, name, score in results[:10]]


# === Extract Subgraph Functions ===
def extract_person_subgraph(g, person_uri):
    """Extract person, their affiliations, abstracts, and abstract authors"""
    entities = {}
    properties = []
    class_attrs = []
    entity_counter = defaultdict(int)

    # Helper to get unique ID
    def get_entity_id(uri, entity_type):
        key = str(uri)
        if key not in entities:
            entity_counter[entity_type] += 1
            return f"{entity_type}{entity_counter[entity_type]}"
        return entities[key]['id']

    # Add the person
    person_name = str(g.value(person_uri, FOAF.name, default="Unknown Person"))
    person_id = get_entity_id(person_uri, "person")
    entities[str(person_uri)] = {
        'id': person_id,
        'type': 'class',
        'iri': str(person_uri),
        'label': person_name
    }

    # Add person's affiliations
    for org_uri in g.objects(person_uri, EX.hasAffiliation):
        org_name = str(g.value(org_uri, SCHEMA.name, default="Unknown Organization"))
        org_id = get_entity_id(org_uri, "org")

        if str(org_uri) not in entities:
            entities[str(org_uri)] = {
                'id': org_id,
                'type': 'class',
                'iri': str(org_uri),
                'label': org_name
            }

        properties.append({
            'id': f"prop_{len(properties)}",
            'type': 'objectProperty',
            'domain': person_id,
            'range': org_id,
            'label': 'hasAffiliation',
            'iri': str(EX.hasAffiliation)
        })

    # Add abstracts where person is author
    for abstract_uri in g.subjects(EX.hasAuthor, person_uri):
        abstract_title = str(g.value(abstract_uri, DCT.title, default="Unknown Abstract"))
        abstract_id = get_entity_id(abstract_uri, "abstract")

        if str(abstract_uri) not in entities:
            entities[str(abstract_uri)] = {
                'id': abstract_id,
                'type': 'class',
                'iri': str(abstract_uri),
                'label': abstract_title[:80]  # Truncate long titles
            }

        properties.append({
            'id': f"prop_{len(properties)}",
            'type': 'objectProperty',
            'domain': abstract_id,
            'range': person_id,
            'label': 'hasAuthor',
            'iri': str(EX.hasAuthor)
        })

        # Add other authors of this abstract
        for other_author_uri in g.objects(abstract_uri, EX.hasAuthor):
            if other_author_uri != person_uri:
                author_name = str(g.value(other_author_uri, FOAF.name, default="Unknown Author"))
                author_id = get_entity_id(other_author_uri, "person")

                if str(other_author_uri) not in entities:
                    entities[str(other_author_uri)] = {
                        'id': author_id,
                        'type': 'class',
                        'iri': str(other_author_uri),
                        'label': author_name
                    }

                # Check if property already exists
                prop_exists = any(
                    p['domain'] == abstract_id and p['range'] == author_id and p['label'] == 'hasAuthor'
                    for p in properties
                )
                if not prop_exists:
                    properties.append({
                        'id': f"prop_{len(properties)}",
                        'type': 'objectProperty',
                        'domain': abstract_id,
                        'range': author_id,
                        'label': 'hasAuthor',
                        'iri': str(EX.hasAuthor)
                    })

    # Add abstracts where person is contact point
    for abstract_uri in g.subjects(DCAT.contactPoint, person_uri):
        abstract_title = str(g.value(abstract_uri, DCT.title, default="Unknown Abstract"))
        abstract_id = get_entity_id(abstract_uri, "abstract")

        if str(abstract_uri) not in entities:
            entities[str(abstract_uri)] = {
                'id': abstract_id,
                'type': 'class',
                'iri': str(abstract_uri),
                'label': abstract_title[:80]
            }

        properties.append({
            'id': f"prop_{len(properties)}",
            'type': 'objectProperty',
            'domain': abstract_id,
            'range': person_id,
            'label': 'contactPoint',
            'iri': str(DCAT.contactPoint)
        })

    return list(entities.values()), properties, class_attrs


def extract_abstract_subgraph(g, abstract_uri):
    """Extract abstract, its authors, their affiliations"""
    entities = {}
    properties = []
    class_attrs = []
    entity_counter = defaultdict(int)

    def get_entity_id(uri, entity_type):
        key = str(uri)
        if key not in entities:
            entity_counter[entity_type] += 1
            return f"{entity_type}{entity_counter[entity_type]}"
        return entities[key]['id']

    # Add the abstract
    abstract_title = str(g.value(abstract_uri, DCT.title, default="Unknown Abstract"))
    abstract_id = get_entity_id(abstract_uri, "abstract")
    entities[str(abstract_uri)] = {
        'id': abstract_id,
        'type': 'class',
        'iri': str(abstract_uri),
        'label': abstract_title
    }

    # Add authors
    for author_uri in g.objects(abstract_uri, EX.hasAuthor):
        author_name = str(g.value(author_uri, FOAF.name, default="Unknown Author"))
        author_id = get_entity_id(author_uri, "person")

        if str(author_uri) not in entities:
            entities[str(author_uri)] = {
                'id': author_id,
                'type': 'class',
                'iri': str(author_uri),
                'label': author_name
            }

        properties.append({
            'id': f"prop_{len(properties)}",
            'type': 'objectProperty',
            'domain': abstract_id,
            'range': author_id,
            'label': 'hasAuthor',
            'iri': str(EX.hasAuthor)
        })

        # Add author's affiliations
        for org_uri in g.objects(author_uri, EX.hasAffiliation):
            org_name = str(g.value(org_uri, SCHEMA.name, default="Unknown Organization"))
            org_id = get_entity_id(org_uri, "org")

            if str(org_uri) not in entities:
                entities[str(org_uri)] = {
                    'id': org_id,
                    'type': 'class',
                    'iri': str(org_uri),
                    'label': org_name
                }

            properties.append({
                'id': f"prop_{len(properties)}",
                'type': 'objectProperty',
                'domain': author_id,
                'range': org_id,
                'label': 'hasAffiliation',
                'iri': str(EX.hasAffiliation)
            })

    # Add contact point
    for contact_uri in g.objects(abstract_uri, DCAT.contactPoint):
        contact_name = str(g.value(contact_uri, FOAF.name, default="Unknown Contact"))
        contact_id = get_entity_id(contact_uri, "person")

        if str(contact_uri) not in entities:
            entities[str(contact_uri)] = {
                'id': contact_id,
                'type': 'class',
                'iri': str(contact_uri),
                'label': contact_name
            }

        properties.append({
            'id': f"prop_{len(properties)}",
            'type': 'objectProperty',
            'domain': abstract_id,
            'range': contact_id,
            'label': 'contactPoint',
            'iri': str(DCAT.contactPoint)
        })

    return list(entities.values()), properties, class_attrs


def extract_organization_subgraph(g, org_uri):
    """Extract organization and affiliated persons with their abstracts"""
    entities = {}
    properties = []
    class_attrs = []
    entity_counter = defaultdict(int)

    def get_entity_id(uri, entity_type):
        key = str(uri)
        if key not in entities:
            entity_counter[entity_type] += 1
            return f"{entity_type}{entity_counter[entity_type]}"
        return entities[key]['id']

    # Add the organization
    org_name = str(g.value(org_uri, SCHEMA.name, default="Unknown Organization"))
    org_id = get_entity_id(org_uri, "org")
    entities[str(org_uri)] = {
        'id': org_id,
        'type': 'class',
        'iri': str(org_uri),
        'label': org_name
    }

    # Add affiliated persons
    for person_uri in g.subjects(EX.hasAffiliation, org_uri):
        person_name = str(g.value(person_uri, FOAF.name, default="Unknown Person"))
        person_id = get_entity_id(person_uri, "person")

        if str(person_uri) not in entities:
            entities[str(person_uri)] = {
                'id': person_id,
                'type': 'class',
                'iri': str(person_uri),
                'label': person_name
            }

        properties.append({
            'id': f"prop_{len(properties)}",
            'type': 'objectProperty',
            'domain': person_id,
            'range': org_id,
            'label': 'hasAffiliation',
            'iri': str(EX.hasAffiliation)
        })

        # Add abstracts by this person
        for abstract_uri in g.subjects(EX.hasAuthor, person_uri):
            abstract_title = str(g.value(abstract_uri, DCT.title, default="Unknown Abstract"))
            abstract_id = get_entity_id(abstract_uri, "abstract")

            if str(abstract_uri) not in entities:
                entities[str(abstract_uri)] = {
                    'id': abstract_id,
                    'type': 'class',
                    'iri': str(abstract_uri),
                    'label': abstract_title[:80]
                }

            prop_exists = any(
                p['domain'] == abstract_id and p['range'] == person_id and p['label'] == 'hasAuthor'
                for p in properties
            )
            if not prop_exists:
                properties.append({
                    'id': f"prop_{len(properties)}",
                    'type': 'objectProperty',
                    'domain': abstract_id,
                    'range': person_id,
                    'label': 'hasAuthor',
                    'iri': str(EX.hasAuthor)
                })

    return list(entities.values()), properties, class_attrs


# === Generate WebVOWL JSON ===
def generate_webvowl_json(classes, properties, class_attrs):
    """Generate WebVOWL-compatible JSON with base class and property definitions"""

    # Add base class definitions that WebVOWL needs
    base_classes = [
        {
            "id": "foaf_Person",
            "type": "owl:Class",
            "iri": str(FOAF.Person),
            "label": "Person"
        },
        {
            "id": "ex_Abstract",
            "type": "owl:Class",
            "iri": str(EX.Abstract),
            "label": "Abstract"
        },
        {
            "id": "schema_Organization",
            "type": "owl:Class",
            "iri": str(SCHEMA.Organization),
            "label": "Organization"
        }
    ]

    # Define base properties that WebVOWL needs
    base_properties = [
        {
            "id": "ex_hasAuthor",
            "type": "owl:ObjectProperty",
            "iri": str(EX.hasAuthor),
            "label": "hasAuthor",
            "domain": "ex_Abstract",
            "range": "foaf_Person"
        },
        {
            "id": "ex_hasAffiliation",
            "type": "owl:ObjectProperty",
            "iri": str(EX.hasAffiliation),
            "label": "hasAffiliation",
            "domain": "foaf_Person",
            "range": "schema_Organization"
        },
        {
            "id": "dcat_contactPoint",
            "type": "owl:ObjectProperty",
            "iri": str(DCAT.contactPoint),
            "label": "contactPoint",
            "domain": "ex_Abstract",
            "range": "foaf_Person"
        },
        {
            "id": "ex_isAuthorOf",
            "type": "owl:ObjectProperty",
            "iri": str(EX.isAuthorOf),
            "label": "isAuthorOf",
            "domain": "foaf_Person",
            "range": "ex_Abstract",
            "inverseOf": "ex_hasAuthor"
        },
        {
            "id": "ex_isAffiliationOf",
            "type": "owl:ObjectProperty",
            "iri": str(EX.isAffiliationOf),
            "label": "isAffiliationOf",
            "domain": "schema_Organization",
            "range": "foaf_Person",
            "inverseOf": "ex_hasAffiliation"
        },
        {
            "id": "ex_isContactFor",
            "type": "owl:ObjectProperty",
            "iri": str(EX.isContactFor),
            "label": "isContactFor",
            "domain": "foaf_Person",
            "range": "ex_Abstract",
            "inverseOf": "dcat_contactPoint"
        }
    ]

    # Combine base classes with instance classes
    all_classes = base_classes + classes

    # Update instances to reference base classes instead of individual types
    for cls in classes:
        if 'person' in cls['id']:
            cls['type'] = 'owl:Class'
            cls['subClassOf'] = 'foaf_Person'
        elif 'abstract' in cls['id']:
            cls['type'] = 'owl:Class'
            cls['subClassOf'] = 'ex_Abstract'
        elif 'org' in cls['id']:
            cls['type'] = 'owl:Class'
            cls['subClassOf'] = 'schema_Organization'

    # Update properties to use correct IDs and reference base property definitions
    property_id_map = {
        str(EX.hasAuthor): "ex_hasAuthor",
        str(EX.hasAffiliation): "ex_hasAffiliation",
        str(DCAT.contactPoint): "dcat_contactPoint",
        str(EX.isAuthorOf): "ex_isAuthorOf",
        str(EX.isAffiliationOf): "ex_isAffiliationOf",
        str(EX.isContactFor): "ex_isContactFor"
    }

    for prop in properties:
        prop['type'] = 'owl:ObjectProperty'
        # Update property ID if it matches a base property
        if prop.get('iri') in property_id_map:
            base_prop_id = property_id_map[prop['iri']]
            prop['subPropertyOf'] = [base_prop_id]

    # Combine base properties with instance properties
    all_properties = base_properties + properties

    return {
        "_comment": "Generated by Knowledge Graph Visualizer",
        "header": {
            "title": "Knowledge Graph Visualization",
            "languages": ["en"],
            "baseIris": ["http://example.org/katalytikertagung/"],
            "iri": "http://example.org/katalytikertagung/visualization"
        },
        "namespace": [],
        "class": all_classes,
        "classAttribute": class_attrs,
        "property": all_properties,
        "propertyAttribute": []
    }


# === GUI Application ===
class KnowledgeGraphVisualizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Knowledge Graph Visualizer")
        self.root.geometry("800x600")

        self.graph = None
        self.current_results = []
        self.output_dir = "visualizations"

        # Create output directory
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.create_widgets()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Load file section
        load_frame = ttk.LabelFrame(main_frame, text="Load Knowledge Graph", padding="10")
        load_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.file_label = ttk.Label(load_frame, text="No file loaded")
        self.file_label.grid(row=0, column=0, sticky=tk.W, padx=5)

        ttk.Button(load_frame, text="Load RDF File", command=self.load_file).grid(row=0, column=1, padx=5)

        # Search type selection
        search_frame = ttk.LabelFrame(main_frame, text="Search Type", padding="10")
        search_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.search_type = tk.StringVar(value="person")
        ttk.Radiobutton(search_frame, text="Person", variable=self.search_type, value="person").grid(row=0, column=0,
                                                                                                     padx=10)
        ttk.Radiobutton(search_frame, text="Abstract", variable=self.search_type, value="abstract").grid(row=0,
                                                                                                         column=1,
                                                                                                         padx=10)
        ttk.Radiobutton(search_frame, text="Organization", variable=self.search_type, value="organization").grid(row=0,
                                                                                                                 column=2,
                                                                                                                 padx=10)

        # Search input
        input_frame = ttk.LabelFrame(main_frame, text="Search Query", padding="10")
        input_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.search_entry = ttk.Entry(input_frame, width=50)
        self.search_entry.grid(row=0, column=0, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search_key)

        ttk.Button(input_frame, text="Search", command=self.perform_search).grid(row=0, column=1, padx=5)

        # Results list
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding="10")
        results_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Scrollbar for results
        scrollbar = ttk.Scrollbar(results_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_listbox = tk.Listbox(results_frame, height=10, yscrollcommand=scrollbar.set)
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.results_listbox.yview)

        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Overwrite existing files", variable=self.overwrite_var).grid(row=0,
                                                                                                          column=0,
                                                                                                          sticky=tk.W)

        # Generate button
        ttk.Button(main_frame, text="Generate Visualization", command=self.generate_visualization).grid(row=5, column=0,
                                                                                                        columnspan=3,
                                                                                                        pady=10)

        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN)
        self.status_label.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def load_file(self):
        """Load RDF file"""
        file_path = filedialog.askopenfilename(
            title="Select RDF File",
            filetypes=[("Turtle files", "*.ttl"), ("RDF files", "*.rdf"), ("All files", "*.*")]
        )

        if file_path:
            try:
                self.graph = load_graph(file_path)
                self.file_label.config(text=f"Loaded: {os.path.basename(file_path)}")
                self.status_label.config(text=f"Loaded {len(self.graph)} triples")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")

    def on_search_key(self, event):
        """Handle keypress in search field for auto-suggestions"""
        # Auto-search after user stops typing (simple debounce simulation)
        if len(self.search_entry.get()) >= 2:
            self.root.after(500, self.perform_search)

    def perform_search(self):
        """Perform search based on selected type"""
        if not self.graph:
            messagebox.showwarning("Warning", "Please load an RDF file first")
            return

        query = self.search_entry.get().strip()
        if not query:
            return

        search_type = self.search_type.get()

        try:
            if search_type == "person":
                results = search_persons(self.graph, query)
            elif search_type == "abstract":
                results = search_abstracts(self.graph, query)
            elif search_type == "organization":
                results = search_organizations(self.graph, query)
            else:
                results = []

            self.current_results = results
            self.update_results_list(results)

            if results:
                self.status_label.config(text=f"Found {len(results)} results")
            else:
                self.status_label.config(text="No results found")
                messagebox.showinfo("No Results", f"No {search_type}s found matching '{query}'")

        except Exception as e:
            messagebox.showerror("Search Error", f"Error during search:\n{str(e)}")

    def update_results_list(self, results):
        """Update the results listbox"""
        self.results_listbox.delete(0, tk.END)
        for uri, name in results:
            self.results_listbox.insert(tk.END, name)

    def generate_visualization(self):
        """Generate WebVOWL JSON for selected result"""
        if not self.current_results:
            messagebox.showwarning("Warning", "No search results available")
            return

        selection = self.results_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a result from the list")
            return

        idx = selection[0]
        selected_uri, selected_name = self.current_results[idx]
        search_type = self.search_type.get()

        try:
            # Extract subgraph based on type
            if search_type == "person":
                classes, properties, class_attrs = extract_person_subgraph(self.graph, selected_uri)
            elif search_type == "abstract":
                classes, properties, class_attrs = extract_abstract_subgraph(self.graph, selected_uri)
            elif search_type == "organization":
                classes, properties, class_attrs = extract_organization_subgraph(self.graph, selected_uri)

            # Generate JSON
            webvowl_data = generate_webvowl_json(classes, properties, class_attrs)

            # Create filename
            safe_name = "".join(c for c in selected_name if c.isalnum() or c in (' ', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')[:50]
            filename = f"{search_type}_{safe_name}.json"
            filepath = os.path.join(self.output_dir, filename)

            # Check if file exists
            if os.path.exists(filepath) and not self.overwrite_var.get():
                response = messagebox.askyesno("File Exists",
                                               f"File '{filename}' already exists.\nDo you want to overwrite it?")
                if not response:
                    return

            # Write JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(webvowl_data, f, indent=2, ensure_ascii=False)

            self.status_label.config(text=f"Generated: {filename}")
            messagebox.showinfo("Success",
                                f"Visualization generated successfully!\n\n"
                                f"File: {filename}\n"
                                f"Location: {os.path.abspath(filepath)}\n\n"
                                f"Entities: {len(classes)}\n"
                                f"Properties: {len(properties)}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate visualization:\n{str(e)}")


# === Main Execution ===
if __name__ == "__main__":
    root = tk.Tk()
    app = KnowledgeGraphVisualizerGUI(root)
    root.mainloop()