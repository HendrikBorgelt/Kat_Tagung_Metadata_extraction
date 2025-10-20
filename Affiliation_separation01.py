import requests
import json
import re


def parse_affiliation_with_ollama(raw_affiliation_string, model_name="qwen3:4b"):
    """
    Connects to a local Ollama instance to parse a raw affiliation string
    into Company, Address, and Country, returning a JSON structure.

    Args:
        raw_affiliation_string (str): The raw string of a single affiliation.
        model_name (str): The name of the model downloaded via Ollama.

    Returns:
        dict: The parsed affiliation as a Python dictionary, or an error message.
    """
    OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

    # Simplified, more concise system prompt
    SYSTEM_PROMPT = (
        "You are a data parser. Extract Company, Address, and Country from affiliation strings. "
        "Return ONLY a JSON object with these three fields. No explanations."
    )

    USER_PROMPT_TEMPLATE = """
Parse this affiliation:
"{raw_affiliation_string}"

Return JSON:
{{
  "Company": "...",
  "Address": "...",
  "Country": "..."
}}
"""

    full_prompt = USER_PROMPT_TEMPLATE.format(raw_affiliation_string=raw_affiliation_string)

    payload = {
        "model": model_name,
        "prompt": full_prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 200  # Limit response length
        }
    }

    try:
        print(f"Sending request to Ollama for: {raw_affiliation_string[:50]}...")

        # Increased timeout and added connection timeout
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=(10, 180)  # (connection timeout, read timeout)
        )
        response.raise_for_status()

        data = response.json()
        json_string = data.get('response', '')

        # Extract JSON object
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_string, re.DOTALL)
        if match:
            clean_json_string = match.group(0)
            parsed = json.loads(clean_json_string)
            print("✓ Successfully parsed")
            return parsed
        else:
            print(f"⚠ Could not extract JSON from response: {json_string[:100]}")
            return {
                "error": "Failed to extract JSON object from LLM response.",
                "raw_output": json_string
            }

    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - is Ollama running?")
        return {
            "error": "Could not connect to Ollama. Run 'ollama serve' in terminal."
        }
    except requests.exceptions.Timeout:
        print("✗ Request timed out")
        return {
            "error": "Request timed out. Try a smaller/faster model or increase timeout."
        }
    except requests.exceptions.RequestException as e:
        print(f"✗ API error: {e}")
        return {"error": f"An API request error occurred: {e}"}
    except json.JSONDecodeError as e:
        print(f"✗ JSON decode error: {e}")
        return {
            "error": f"Failed to decode JSON: {e}",
            "raw_output": json_string
        }


def test_ollama_connection(model_name="qwen3:4b"):
    """Test if Ollama is running and responsive."""
    OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

    print(f"Testing connection to Ollama with model '{model_name}'...")

    payload = {
        "model": model_name,
        "prompt": "Say 'OK'",
        "stream": False,
        "options": {"num_predict": 5}
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=(5, 30))
        response.raise_for_status()
        print("✓ Ollama is running and responsive!")
        return True
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to Ollama. Start it with: ollama serve")
        return False
    except requests.exceptions.Timeout:
        print("✗ Ollama is not responding. It may be loading the model.")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


# --- Example Usage ---
if __name__ == "__main__":
    # First test the connection
    # if not test_ollama_connection():
    #     print("\nPlease start Ollama before running this script.")
    #     print("1. Open a terminal")
    #     print("2. Run: ollama serve")
    #     print("3. In another terminal, run: ollama pull qwen3:4b")
    #     exit(1)

    print("\n" + "=" * 60)

    raw_affiliation_1 = "School of Electrical Engineering, University of New South Wales, Sydney, NSW, Australia"
    raw_affiliation_2 = "Institut für Chemische Technologie, WACKER Chemie AG, Burghausen, Germany"

    print("\n--- Affiliation 1 ---")
    parsed_affil_1 = parse_affiliation_with_ollama(raw_affiliation_1)
    print(json.dumps(parsed_affil_1, indent=2))

    print("\n--- Affiliation 2 ---")
    parsed_affil_2 = parse_affiliation_with_ollama(raw_affiliation_2)
    print(json.dumps(parsed_affil_2, indent=2))