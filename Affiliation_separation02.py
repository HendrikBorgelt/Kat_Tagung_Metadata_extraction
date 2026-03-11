import ollama

client = ollama.Client()

prompt =' test'

response = client.chat(
    model='qwen3:4b', # Use a fast, quantized model
    messages=[
        {
            'role': 'system',
            # Force JSON output and conciseness
            'content': 'You are a data cleaner. Extract and structure the data into a JSON array. DO NOT include any extra text.',
        },
        {
            'role': 'user',
            'content': prompt,
        }
    ],
    options={
        # Set a hard limit on the number of generated tokens (e.g., 512)
        'num_predict': 8000,
        # Force the model to output JSON if it supports it
        'format': 'json',
        # Higher temperature can sometimes lead to less verbose, more direct answers, but can reduce quality
        'temperature': 0.1
    }
)

print(response['message']['content'])