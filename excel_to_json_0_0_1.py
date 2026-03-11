import pandas as pd
import json
import sys

# --- Configuration ---
INPUT_EXCEL_FILE = 'metadata_accaptable_for_llm.xlsx'  # Your Excel file name
OUTPUT_JSON_FILE = 'metadata_accaptable_for_llm.json'
AUTHOR_COLUMN = 'foaf:agent'
ORGANIZATION_COLUMN = 'schema:Organization'
RELATION_COLUMN = 'dct:relation'  # <-- Added this for publications


# ---------------------

def process_excel(input_file, output_file):
    """
    Reads an Excel file, processes authors, organizations, and relations,
    and writes the result to a JSON file.
    """
    processed_data = []

    try:
        # Read the Excel file
        df = pd.read_excel(input_file)

        # Convert NaN (empty cells) to empty strings for safe processing
        df = df.fillna('')

        # Convert the DataFrame to a list of dictionaries
        reader = df.to_dict('records')

    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        print("Please make sure it's in the same directory as the script.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while reading the Excel file: {e}")
        print("Please ensure 'pandas' and 'openpyxl' are installed (`pip install pandas openpyxl`)")
        sys.exit(1)

    # Process each row
    for row in reader:
        # 1. Process Organizations
        org_string = row.get(ORGANIZATION_COLUMN, '')
        organizations = [org.strip() for org in org_string.split(';') if org.strip()]

        # 2. Process Authors
        agent_string = row.get(AUTHOR_COLUMN, '')
        agent_string_normalized = agent_string.replace(' and ', ', ')
        author_names = [name.strip().strip(',') for name in agent_string_normalized.split(',') if name.strip()]

        authors_list = []
        for name in author_names:
            authors_list.append({
                'name': name,
                'affiliations': organizations
            })

        # 3. NEW: Process Relations (Publications)
        relation_string = row.get(RELATION_COLUMN, '')

        # Split by semicolon, then strip whitespace/newlines from each item.
        # Filter out any empty strings that result (e.g., from a trailing ';')
        publications_list = [pub.strip() for pub in relation_string.split(';') if pub.strip()]

        # 4. Build the new output row
        output_row = {}
        for key, value in row.items():
            # Copy all columns *except* the ones we are replacing/reformatting
            if key not in [AUTHOR_COLUMN, ORGANIZATION_COLUMN, RELATION_COLUMN]:
                output_row[key] = value

        # Add our new, structured lists
        output_row['authors'] = authors_list
        output_row[RELATION_COLUMN] = publications_list  # <-- Add the new list

        processed_data.append(output_row)

    # 5. Write the result to a JSON file
    try:
        with open(output_file, mode='w', encoding='utf-8') as file:
            json.dump(processed_data, file, indent=4, ensure_ascii=False)

        print(f"Success! Processed {len(processed_data)} rows.")
        print(f"Data has been written to '{output_file}'.")

    except Exception as e:
        print(f"An error occurred while writing the JSON file: {e}")
        sys.exit(1)


# --- Run the script ---
if __name__ == "__main__":
    process_excel(INPUT_EXCEL_FILE, OUTPUT_JSON_FILE)