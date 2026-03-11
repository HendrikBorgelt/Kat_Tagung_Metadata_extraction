import json
from collections import defaultdict, Counter
from difflib import SequenceMatcher


def extract_affiliations(json_file_path):
    """Extract all affiliations from the JSON file."""
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    affiliations = []
    for entry in data:
        if 'authors' in entry:
            for author in entry['authors']:
                if 'affiliations' in author:
                    affiliations.extend(author['affiliations'])

    return affiliations


def similarity_score(str1, str2):
    """Calculate similarity between two strings (0-1 scale)."""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def group_similar_affiliations(affiliations, threshold=0.85):
    """
    Group similar affiliations together.

    Args:
        affiliations: List of affiliation strings
        threshold: Similarity threshold (0-1), default 0.85

    Returns:
        Dictionary with most common variant as key and list of similar variants with counts
    """
    # Count occurrences of each affiliation
    affiliation_counts = Counter(affiliations)

    # Group similar affiliations
    groups = []
    processed = set()

    for affiliation in affiliation_counts.keys():
        if affiliation in processed:
            continue

        # Find all similar affiliations
        similar = {affiliation: affiliation_counts[affiliation]}
        processed.add(affiliation)

        for other_affiliation in affiliation_counts.keys():
            if other_affiliation not in processed:
                if similarity_score(affiliation, other_affiliation) >= threshold:
                    similar[other_affiliation] = affiliation_counts[other_affiliation]
                    processed.add(other_affiliation)

        groups.append(similar)

    # Create final dictionary with most common variant as key
    result = {}
    for group in groups:
        # Find the most common affiliation in this group
        most_common = max(group.items(), key=lambda x: x[1])[0]

        # Convert to list of dicts format
        variants_list = [{aff: count} for aff, count in sorted(
            group.items(),
            key=lambda x: x[1],
            reverse=True
        )]

        result[most_common] = variants_list

    return result


def main(json_file_path, output_file_path='affiliation_groups.json', threshold=0.75):
    """
    Main function to extract, group, and save affiliations.

    Args:
        json_file_path: Path to input JSON file
        output_file_path: Path to save output JSON file
        threshold: Similarity threshold for grouping (default 0.85)
    """
    print(f"Extracting affiliations from {json_file_path}...")
    affiliations = extract_affiliations(json_file_path)
    print(f"Found {len(affiliations)} total affiliations")
    print(f"Found {len(set(affiliations))} unique affiliations")

    print(f"\nGrouping similar affiliations (threshold: {threshold})...")
    grouped = group_similar_affiliations(affiliations, threshold)

    print(f"Grouped into {len(grouped)} clusters\n")

    # Print summary
    print("Summary of groups:")
    print("-" * 80)
    for key, variants in grouped.items():
        total_count = sum(list(v.values())[0] for v in variants)
        print(f"\n'{key}' ({total_count} total occurrences):")
        for variant in variants:
            for aff, count in variant.items():
                print(f"  - '{aff}': {count}")

    # Save to file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(grouped, f, indent=2, ensure_ascii=False)

    print(f"\n\nResults saved to {output_file_path}")

    return grouped


# Example usage
if __name__ == "__main__":
    # Adjust the file path to your JSON file
    input_file = "metadata_output_20251023_1016_cleaned_affiliations3.json"
    output_file = "affiliation_groups3.json"

    # You can adjust the threshold:
    # - Higher (0.9-0.95): Only very similar strings are grouped
    # - Lower (0.75-0.85): More aggressive grouping
    grouped_affiliations = main(input_file, output_file, threshold=0.70)