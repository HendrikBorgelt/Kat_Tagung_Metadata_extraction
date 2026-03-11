import pandas as pd
import json
import sys

# --- Configuration ---
INPUT_EXCEL_FILE = 'metadata_output_for_conversion_20251014_1508.xlsx'  # Your Excel file name
OUTPUT_JSON_FILE = 'metadata_output_for_conversion_20251014_1508.json'
AUTHOR_COLUMN = 'foaf:agent'
ORGANIZATION_COLUMN = 'schema:Organization'


# ---------------------

def process_excel(input_file, output_file):
    """
    Reads an Excel file, processes author and organization data,
    and writes the result to a JSON file.
    """
    processed_data = []

    try:
        # 1. Read the Excel file using pandas
        # By default, this reads the first sheet
        df = pd.read_excel(input_file)

        # 2. IMPORTANT: Convert NaN (empty cells) to empty strings
        # This makes processing much easier and avoids errors
        df = df.fillna('')

        # 3. Convert the DataFrame to a list of dictionaries (like csv.DictReader)
        reader = df.to_dict('records')

    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        print("Please make sure it's in the same directory as the script.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while reading the Excel file: {e}")
        print("Please ensure 'pandas' and 'openpyxl' are installed (`pip install pandas openpyxl`)")
        sys.exit(1)

    # 4. Process each row (This logic is the same as before)
    for row in reader:
        # Get the string from the organization column
        org_string = row.get(ORGANIZATION_COLUMN, '')

        # Split by semicolon and strip whitespace.
        organizations = [org.strip() for org in org_string.split(';') if org.strip()]

        # Get the string from the author column
        agent_string = row.get(AUTHOR_COLUMN, '')

        # Replace " and " with a comma to standardize the separator
        agent_string_normalized = agent_string.replace(' and ', ', ')

        # Split by comma and strip whitespace/lingering commas.
        author_names = [name.strip().strip(',') for name in agent_string_normalized.split(',') if name.strip()]

        # Create new author list with affiliations
        authors_list = []
        for name in author_names:
            author_obj = {
                'name': name,
                'affiliations': organizations  # Assign the full list to each author
            }
            authors_list.append(author_obj)

        # Build the new output row
        output_row = {}
        for key, value in row.items():
            if key not in [AUTHOR_COLUMN, ORGANIZATION_COLUMN]:
                output_row[key] = value

        # Add our new, structured list
        output_row['authors'] = authors_list

        processed_data.append(output_row)

    # 5. Write the result to a JSON file (This logic is also the same)
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
    # Make sure your Excel file is named 'input.xlsx'
    # or change the variable at the top of the script.
    process_excel(INPUT_EXCEL_FILE, OUTPUT_JSON_FILE)