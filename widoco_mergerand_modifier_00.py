#!/usr/bin/env python3
"""
Widoco Documentation Merger
This script generates two Widoco documentations and merges their WebVOWL folders.
"""

import subprocess
import shutil
import json
from pathlib import Path

# ============================================================
# CONFIGURATION SECTION - Edit your settings here
# ============================================================

# File paths
MAIN_TTL = "katalytikertagung_instances.ttl"
SECONDARY_TTL = "katalytikertagung_ontology.ttl"
OUTPUT_DIR = "doc"
WIDOCO_JAR = "widoco-1.4.25-jar-with-dependencies_JDK-17.jar"

# Configuration files (optional - set to None if not using)
MAIN_CONFIG = "config_instances.json"  # or None
SECONDARY_CONFIG = "config_ontology.json"  # or None

# Options
LANGUAGE = "en"  # Language for documentation (e.g., "en", "de", "es")
INCLUDE_DIAGRAMS = True  # Include class diagrams
CLEANUP_SECONDARY = True  # Delete secondary documentation after merging

# Widoco command options
WIDOCO_OPTIONS = {
    "rewrite_all": True,  # Overwrite existing files
    "include_webvowl": True,  # Generate WebVOWL visualization
    "unite_sections": True,  # Unite all sections in one document
    "include_imported": True,  # Include imported ontologies
    "include_annotations": True,  # Include annotation properties
}

# Configuration for creating default config files
CREATE_DEFAULT_CONFIGS = False  # Set to True to generate default config files

DEFAULT_CONFIG_MAIN = {
    "title": "Katalytikertagung Instances",
    "prefix": "kti",
    "namespace": "http://example.org/katalytikertagung/instances#",
    "name": "KatalytikertagungInstances",
    "abstract": "This ontology contains instances for the Katalytikertagung.",
    "authors": [
        {
            "authorName": "Your Name",
            "authorURL": "http://example.org/you",
            "authorInstitution": "Your Institution",
            "authorInstitutionURI": "http://example.org/institution"
        }
    ],
    "languages": "en,de",
}

DEFAULT_CONFIG_SECONDARY = {
    "title": "Katalytikertagung Ontology",
    "prefix": "kto",
    "namespace": "http://example.org/katalytikertagung/ontology#",
    "name": "KatalytikertagungOntology",
    "abstract": "This ontology defines the schema for the Katalytikertagung.",
    "authors": [
        {
            "authorName": "Your Name",
            "authorURL": "http://example.org/you",
            "authorInstitution": "Your Institution",
            "authorInstitutionURI": "http://example.org/institution"
        }
    ],
    "languages": "en,de",
}


# ============================================================
# END OF CONFIGURATION SECTION
# ============================================================


class WidocoMerger:
    """Main class for merging Widoco documentations."""

    def __init__(self, main_ttl, secondary_ttl, output_dir, main_config=None, secondary_config=None):
        self.main_ttl = Path(main_ttl)
        self.secondary_ttl = Path(secondary_ttl)
        self.output_dir = Path(output_dir)
        self.main_config = Path(main_config) if main_config else None
        self.secondary_config = Path(secondary_config) if secondary_config else None

        self.main_doc_dir = self.output_dir / "main_doc"
        self.secondary_doc_dir = self.output_dir / "secondary_doc"

    def generate_widoco_doc(self, ttl_file, output_path, config_file=None):
        """Generate Widoco documentation for a given TTL file."""
        print(f"Generating Widoco documentation for {ttl_file}...")

        output_path.mkdir(parents=True, exist_ok=True)

        # Build Widoco command
        cmd = [
            "java", "-jar", WIDOCO_JAR,
            "-ontFile", str(ttl_file),
            "-outFolder", str(output_path),
            "-lang", LANGUAGE,
        ]

        # Add optional flags based on configuration
        if WIDOCO_OPTIONS["rewrite_all"]:
            cmd.append("-rewriteAll")
        if WIDOCO_OPTIONS["include_webvowl"]:
            cmd.append("-webVowl")
        if WIDOCO_OPTIONS["unite_sections"]:
            cmd.append("-uniteSections")
        if WIDOCO_OPTIONS["include_imported"]:
            cmd.append("-includeImportedOntologies")
        if WIDOCO_OPTIONS["include_annotations"]:
            cmd.append("-includeAnnotationProperties")

        # Add configuration file if provided
        if config_file and config_file.exists():
            cmd.extend(["-confFile", str(config_file)])
            print(f"  Using config file: {config_file}")

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"✓ Documentation generated successfully in {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Error generating documentation: {e}")
            print(f"Error output: {e.stderr}")
            return False

    def merge_webvowl(self):
        """Merge the WebVOWL folder from secondary documentation into main documentation."""
        print("\nMerging WebVOWL folders...")

        source_webvowl = self.secondary_doc_dir / "webvowl"
        target_webvowl = self.main_doc_dir / "webvowl"

        if not source_webvowl.exists():
            print(f"✗ Source WebVOWL folder not found: {source_webvowl}")
            return False

        if target_webvowl.exists():
            print(f"  Removing existing WebVOWL folder: {target_webvowl}")
            shutil.rmtree(target_webvowl)

        try:
            shutil.copytree(source_webvowl, target_webvowl)
            print(f"✓ WebVOWL folder merged successfully")
            return True
        except Exception as e:
            print(f"✗ Error merging WebVOWL folders: {e}")
            return False

    def cleanup_secondary_doc(self):
        """Remove the secondary documentation folder after merging."""
        if not CLEANUP_SECONDARY:
            print("\nSkipping cleanup (CLEANUP_SECONDARY is False)")
            return True

        print(f"\nCleaning up secondary documentation...")

        if self.secondary_doc_dir.exists():
            try:
                shutil.rmtree(self.secondary_doc_dir)
                print(f"✓ Secondary documentation removed: {self.secondary_doc_dir}")
                return True
            except Exception as e:
                print(f"✗ Error removing secondary documentation: {e}")
                return False
        else:
            print(f"  Secondary documentation folder not found: {self.secondary_doc_dir}")
            return False

    def run(self):
        """Execute the complete merging process."""
        print("=" * 60)
        print("Widoco Documentation Merger")
        print("=" * 60)

        # Step 1: Generate main documentation
        print("\n[1/5] Generating main documentation...")
        if not self.generate_widoco_doc(self.main_ttl, self.main_doc_dir, self.main_config):
            print("Failed to generate main documentation. Aborting.")
            return False

        # Step 2: Generate secondary documentation
        print("\n[2/5] Generating secondary documentation...")
        if not self.generate_widoco_doc(self.secondary_ttl, self.secondary_doc_dir, self.secondary_config):
            print("Failed to generate secondary documentation. Aborting.")
            return False

        # Step 3: Merge WebVOWL folders
        print("\n[3/5] Merging WebVOWL folders...")
        if not self.merge_webvowl():
            print("Failed to merge WebVOWL folders.")
            return False

        # Step 4: Cleanup secondary documentation
        print("\n[4/5] Cleaning up...")
        self.cleanup_secondary_doc()

        # Step 5: Done
        print("\n[5/5] Process completed!")
        print("=" * 60)
        print(f"\nMerged documentation available at: {self.main_doc_dir}")
        print(f"Main index file: {self.main_doc_dir / 'index-en.html'}")
        print("=" * 60)

        return True


def create_config_file(config_dict, output_path):
    """Create a Widoco configuration file."""
    full_config = {
        "ontologyTitle": config_dict.get("title", "My Ontology"),
        "ontologyPrefix": config_dict.get("prefix", "myonto"),
        "ontologyNamespaceURI": config_dict.get("namespace", "http://example.org/ontology#"),
        "ontologyName": config_dict.get("name", "MyOntology"),
        "dateOfRelease": config_dict.get("date", "2024-01-01"),
        "ontologyRevisionNumber": config_dict.get("revision", "1.0.0"),
        "licenseURI": config_dict.get("license", "http://creativecommons.org/licenses/by/4.0/"),
        "licenseName": config_dict.get("license_name", "CC BY 4.0"),
        "authors": config_dict.get("authors", []),
        "languages": config_dict.get("languages", "en"),
        "abstract": config_dict.get("abstract", "This ontology..."),
    }

    with open(output_path, 'w') as f:
        json.dump(full_config, f, indent=2)

    print(f"✓ Configuration file created: {output_path}")


def create_default_configs():
    """Create default configuration files."""
    print("Creating default configuration files...")
    create_config_file(DEFAULT_CONFIG_MAIN, "config_instances.json")
    create_config_file(DEFAULT_CONFIG_SECONDARY, "config_ontology.json")
    print("\nDefault configuration files created:")
    print("  - config_instances.json")
    print("  - config_ontology.json")
    print("\nPlease edit these files with your ontology details before running the merger.")


def validate_setup():
    """Validate that all required files exist."""
    errors = []

    if not Path(MAIN_TTL).exists():
        errors.append(f"Main TTL file not found: {MAIN_TTL}")

    if not Path(SECONDARY_TTL).exists():
        errors.append(f"Secondary TTL file not found: {SECONDARY_TTL}")

    if not Path(WIDOCO_JAR).exists():
        errors.append(f"Widoco JAR not found: {WIDOCO_JAR}")
        errors.append("  Download from: https://github.com/dgarijo/Widoco/releases")

    if MAIN_CONFIG and not Path(MAIN_CONFIG).exists():
        print(f"Warning: Main config file not found: {MAIN_CONFIG}")
        print("  Proceeding without main config file...")

    if SECONDARY_CONFIG and not Path(SECONDARY_CONFIG).exists():
        print(f"Warning: Secondary config file not found: {SECONDARY_CONFIG}")
        print("  Proceeding without secondary config file...")

    if errors:
        print("Error: Missing required files:")
        for error in errors:
            print(f"  {error}")
        return False

    return True


def main():
    """Main function to run the script."""

    # Create default configs if requested
    if CREATE_DEFAULT_CONFIGS:
        create_default_configs()
        return

    # Validate setup
    if not validate_setup():
        return

    # Create merger instance and run
    merger = WidocoMerger(
        MAIN_TTL,
        SECONDARY_TTL,
        OUTPUT_DIR,
        main_config=MAIN_CONFIG,
        secondary_config=SECONDARY_CONFIG
    )

    merger.run()


if __name__ == "__main__":
    main()