#!/usr/bin/env python3
"""
Widoco Documentation Merger
This script generates two Widoco documentations and merges their WebVOWL folders.
"""

import subprocess
import shutil
import os
from pathlib import Path


class WidocoMerger:
    def __init__(self, main_ttl, secondary_ttl, output_dir="doc"):
        """
        Initialize the Widoco merger.

        Args:
            main_ttl: Path to the main TTL file (katalytikertagung_instances.ttl)
            secondary_ttl: Path to the secondary TTL file (katalytikertagung_ontology.ttl)
            output_dir: Base directory for documentation output
        """
        self.main_ttl = Path(main_ttl)
        self.secondary_ttl = Path(secondary_ttl)
        self.output_dir = Path(output_dir)

        # Define output directories
        self.main_doc_dir = self.output_dir / "main_doc"
        self.secondary_doc_dir = self.output_dir / "secondary_doc"

    def generate_widoco_doc(self, ttl_file, output_path, widoco_jar="widoco.jar"):
        """
        Generate Widoco documentation for a given TTL file.

        Args:
            ttl_file: Path to the TTL file
            output_path: Output directory for the documentation
            widoco_jar: Path to the Widoco JAR file
        """
        print(f"Generating Widoco documentation for {ttl_file}...")

        # Create output directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)

        # Widoco command
        cmd = [
            "java", "-jar", widoco_jar,
            "-ontFile", str(ttl_file),
            "-outFolder", str(output_path),
            "-rewriteAll",  # Overwrite existing files
            "-includeImportedOntologies",  # Include imported ontologies
            "-webVowl"  # Generate WebVOWL visualization
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✓ Documentation generated successfully in {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Error generating documentation: {e}")
            print(f"Error output: {e.stderr}")
            return False

    def merge_webvowl(self):
        """
        Merge the WebVOWL folder from secondary documentation into main documentation.
        """
        print("\nMerging WebVOWL folders...")

        source_webvowl = self.secondary_doc_dir / "webvowl"
        target_webvowl = self.main_doc_dir / "webvowl"

        if not source_webvowl.exists():
            print(f"✗ Source WebVOWL folder not found: {source_webvowl}")
            return False

        if target_webvowl.exists():
            print(f"Removing existing WebVOWL folder: {target_webvowl}")
            shutil.rmtree(target_webvowl)

        try:
            # Copy the entire WebVOWL directory
            shutil.copytree(source_webvowl, target_webvowl)
            print(f"✓ WebVOWL folder merged successfully")
            return True
        except Exception as e:
            print(f"✗ Error merging WebVOWL folders: {e}")
            return False

    def cleanup_secondary_doc(self):
        """
        Remove the secondary documentation folder after merging.
        """
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
            print(f"Secondary documentation folder not found: {self.secondary_doc_dir}")
            return False

    def run(self, widoco_jar="widoco.jar"):
        """
        Execute the complete merging process.

        Args:
            widoco_jar: Path to the Widoco JAR file
        """
        print("=" * 60)
        print("Widoco Documentation Merger")
        print("=" * 60)

        # Step 1: Generate main documentation
        print("\n[1/5] Generating main documentation...")
        if not self.generate_widoco_doc(self.main_ttl, self.main_doc_dir, widoco_jar):
            print("Failed to generate main documentation. Aborting.")
            return False

        # Step 2: Generate secondary documentation
        print("\n[2/5] Generating secondary documentation...")
        if not self.generate_widoco_doc(self.secondary_ttl, self.secondary_doc_dir, widoco_jar):
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
        print(f"You can now modify the index.html file at: {self.main_doc_dir / 'index-en.html'}")
        print("=" * 60)

        return True


def main():
    """Main function to run the script."""

    # Configuration
    MAIN_TTL = "katalytikertagung_instances.ttl"
    SECONDARY_TTL = "katalytikertagung_ontology.ttl"
    OUTPUT_DIR = "doc"
    WIDOCO_JAR = "widoco.jar"  # Adjust path if needed

    # Check if TTL files exist
    if not Path(MAIN_TTL).exists():
        print(f"Error: Main TTL file not found: {MAIN_TTL}")
        return

    if not Path(SECONDARY_TTL).exists():
        print(f"Error: Secondary TTL file not found: {SECONDARY_TTL}")
        return

    if not Path(WIDOCO_JAR).exists():
        print(f"Warning: Widoco JAR not found at: {WIDOCO_JAR}")
        print("Please ensure widoco.jar is in the current directory or update WIDOCO_JAR variable.")
        print("You can download it from: https://github.com/dgarijo/Widoco/releases")
        return

    # Create merger instance and run
    merger = WidocoMerger(MAIN_TTL, SECONDARY_TTL, OUTPUT_DIR)
    merger.run(WIDOCO_JAR)


if __name__ == "__main__":
    main()