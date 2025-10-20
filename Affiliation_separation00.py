import requests
import json
import re  # Added for robust JSON parsing


def parse_affiliation_with_ollama(raw_affiliation_string, model_name="qwen3:4b"):
    """
    Connects to a local Ollama instance to parse a raw affiliation string
    into Company, Address, and Country, returning a JSON structure.

    Args:
        raw_affiliation_string (str): The raw string of a single affiliation.
        model_name (str): The name of the model downloaded via Ollama.

    Returns:
        dict or str: The parsed affiliation as a Python dictionary, or an error message.
    """
    # Ollama's default API endpoint for generating responses
    OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

    # --- 1. System Prompt (Defines the Rules) ---
    SYSTEM_PROMPT = (
        """
        You are an expert data parsing and structuring assistant. Your sole task is to analyze a raw academic or corporate affiliation string and strictly separate it into three distinct components: 'Company', 'Address', and 'Country'.
    
        RULES:
        1.  **Company (Institution/Corporation):** This must be the main name of the entity (e.g., 'Massachusetts Institute of Technology', 'Department of Chemistry', 'Fraunhofer ISE').
        2.  **Country:** This must be the official or common name of the country (e.g., 'Germany', 'USA', 'China').
        3.  **Address:** This is everything else, typically the street address, city, state, and postal/zip code.
        4.  **Output Format:** You MUST return the result as a single JSON object. Do not include any text, explanations, or quotes outside of the JSON object.
        """
    )

    # --- 2. User Prompt (The Request Template) ---
    USER_PROMPT_TEMPLATE = """
    Please process the following raw affiliation string and return the result in the specified JSON format.

    RAW AFFILIATION STRING:
    "{raw_affiliation_string}"

    REQUIRED JSON FORMAT:
    {{
      "Company": "...",
      "Address": "...",
      "Country": "..."
    }}
    """

    # --- 3. Construct the full prompt for the API ---
    full_prompt = USER_PROMPT_TEMPLATE.format(raw_affiliation_string=raw_affiliation_string)

    payload = {
        "model": model_name,
        "prompt": full_prompt,  # Use the correctly formatted user prompt
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
        response.raise_for_status()

        data = response.json()

        # The raw response text (which should be a JSON string)
        json_string = data.get('response', 'Error: No response text found.')

        # Robustly extract only the JSON object, as LLMs sometimes add ```json delimiters
        match = re.search(r'\{.*\}', json_string, re.DOTALL)
        if match:
            clean_json_string = match.group(0)
            return json.loads(clean_json_string)
        else:
            return {"error": "Failed to extract JSON object from LLM response.", "raw_output": json_string}

    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to Ollama. Ensure Ollama is running and the model is loaded."}
    except requests.exceptions.RequestException as e:
        return {"error": f"An API request error occurred: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"Failed to decode JSON from LLM output: {e}", "raw_output": json_string}


# --- Example Usage ---
raw_affiliation_1 = "School of Electrical Engineering, University of New South Wales, Sydney, NSW, Australia"
raw_affiliation_2 = "Institut für Chemische Technologie, WACKER Chemie AG, Burghausen, Germany"

print("--- Affiliation 1 ---")
parsed_affil_1 = parse_affiliation_with_ollama(raw_affiliation_1)
print(json.dumps(parsed_affil_1, indent=2))

print("\n--- Affiliation 2 ---")
parsed_affil_2 = parse_affiliation_with_ollama(raw_affiliation_2)
print(json.dumps(parsed_affil_2, indent=2))