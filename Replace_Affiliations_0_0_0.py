import json


def load_json_file(filepath):
    """Load JSON data from a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(data, filepath):
    """Save JSON data to a file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def build_affiliation_mapping(affiliation_groups):
    """
    Build a mapping from variant affiliations to their canonical form.

    Args:
        affiliation_groups: Dict where keys are canonical affiliations
                          and values are lists of dicts with variants

    Returns:
        Dict mapping variant affiliations to canonical affiliations
    """
    mapping = {}

    for canonical_affiliation, variants in affiliation_groups.items():
        # Add the canonical form itself
        mapping[canonical_affiliation] = canonical_affiliation

        # Add all variants
        for variant_dict in variants:
            for variant_affiliation in variant_dict.keys():
                mapping[variant_affiliation] = canonical_affiliation

    return mapping


def clean_affiliations(metadata, affiliation_mapping):
    """
    Clean affiliations in the metadata using the affiliation mapping.

    Args:
        metadata: List of metadata dicts with author affiliations
        affiliation_mapping: Dict mapping variant to canonical affiliations

    Returns:
        Cleaned metadata with standardized affiliations
    """
    cleaned_metadata = []

    for entry in metadata:
        cleaned_entry = entry.copy()

        if 'authors' in cleaned_entry:
            cleaned_authors = []

            for author in cleaned_entry['authors']:
                cleaned_author = author.copy()

                if 'affiliations' in cleaned_author:
                    cleaned_affiliations = []

                    for affiliation in cleaned_author['affiliations']:
                        # Look up the canonical form
                        canonical = affiliation_mapping.get(affiliation, affiliation)
                        cleaned_affiliations.append(canonical)

                    cleaned_author['affiliations'] = cleaned_affiliations

                cleaned_authors.append(cleaned_author)

            cleaned_entry['authors'] = cleaned_authors

        cleaned_metadata.append(cleaned_entry)

    return cleaned_metadata


def main():
    # File paths
    affiliation_groups_file = 'affiliation_groups2.json'
    metadata_file = 'metadata_output_20251023_1016_cleaned_affiliations2.json'
    output_file = 'metadata_output_20251023_1016_cleaned_affiliations3.json'

    # Load data
    print("Loading affiliation groups...")
    affiliation_groups = load_json_file(affiliation_groups_file)

    print("Loading metadata...")
    metadata = load_json_file(metadata_file)

    # Build mapping
    print("Building affiliation mapping...")
    affiliation_mapping = build_affiliation_mapping(affiliation_groups)
    print(f"Created mapping with {len(affiliation_mapping)} affiliations")

    # Clean affiliations
    print("Cleaning affiliations in metadata...")
    cleaned_metadata = clean_affiliations(metadata, affiliation_mapping)

    # Save cleaned data
    print(f"Saving cleaned metadata to {output_file}...")
    save_json_file(cleaned_metadata, output_file)

    print("Done! Affiliations have been cleaned and saved.")

    # Print summary
    print("\nSummary of changes:")
    for i, (original, cleaned) in enumerate(zip(metadata, cleaned_metadata)):
        if 'authors' in original:
            for j, (orig_author, clean_author) in enumerate(zip(original['authors'], cleaned['authors'])):
                if orig_author.get('affiliations') != clean_author.get('affiliations'):
                    print(f"\nEntry {i + 1}, Author: {orig_author['name']}")
                    print(f"  Original: {orig_author.get('affiliations', [])}")
                    print(f"  Cleaned:  {clean_author.get('affiliations', [])}")


if __name__ == "__main__":
    main()