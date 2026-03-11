#!/usr/bin/env python3
"""
Ollama Chat/Batch Script
Interact with Ollama's Qwen 3 4B model in chat or batch mode
"""

import requests
import json
import sys
from typing import List, Dict


class OllamaClient:
    def __init__(self, model: str = "qwen3:4b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.chat_history = []

    def send_message(self, prompt: str, use_history: bool = True) -> str:
        """Send a message to Ollama and get a response"""

        # Prepare the message
        if use_history:
            messages = self.chat_history + [{"role": "user", "content": prompt}]
        else:
            messages = [{"role": "user", "content": prompt}]

        # Send request to Ollama
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            assistant_message = result["message"]["content"]

            # Update chat history if using it
            if use_history:
                self.chat_history.append({"role": "user", "content": prompt})
                self.chat_history.append({"role": "assistant", "content": assistant_message})

            return assistant_message

        except requests.exceptions.RequestException as e:
            return f"Error communicating with Ollama: {e}"

    def clear_history(self):
        """Clear the chat history"""
        self.chat_history = []

    def chat_mode(self):
        """Interactive chat mode"""
        print(f"=== Ollama Chat Mode ({self.model}) ===")
        print("Type 'exit' or 'quit' to end the chat")
        print("Type 'clear' to clear chat history")
        print("=" * 50)

        while True:
            try:
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['exit', 'quit']:
                    print("Goodbye!")
                    break

                if user_input.lower() == 'clear':
                    self.clear_history()
                    print("Chat history cleared!")
                    continue

                print("\nAssistant: ", end="", flush=True)
                response = self.send_message(user_input, use_history=True)
                print(response)

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")

    def batch_mode(self, prompts: List[str], use_history: bool = False):
        """Process a list of prompts in batch"""
        print(f"=== Ollama Batch Mode ({self.model}) ===")
        print(f"Processing {len(prompts)} prompts...")
        print("=" * 50)

        results = []

        for i, prompt in enumerate(prompts, 1):
            print(f"\n[Prompt {i}/{len(prompts)}]")
            print(f"Input: {prompt}")
            print("-" * 50)

            response = self.send_message(prompt, use_history=use_history)
            print(f"Response: {response}")

            results.append({
                "prompt": prompt,
                "response": response
            })

        print("\n" + "=" * 50)
        print("Batch processing complete!")

        return results


def main():
    # Initialize client
    client = OllamaClient(model="qwen3:4b")

    print("Ollama Client for Qwen 3 4B")
    print("=" * 50)
    print("Choose mode:")
    print("1. Chat mode (interactive)")
    print("2. Batch mode (list of prompts)")

    choice = input("\nEnter choice (1 or 2): ").strip()

    if choice == "1":
        client.chat_mode()

    elif choice == "2":
        print("\n=== Batch Mode Setup ===")
        print("Enter your prompts (one per line)")
        print("Type 'DONE' on a new line when finished")
        print()

        prompts = []
        while True:
            line = input(f"Prompt {len(prompts) + 1}: ").strip()
            if line.upper() == "DONE":
                break
            if line:
                prompts.append(line)

        if not prompts:
            print("No prompts provided. Exiting.")
            return

        use_history = input("\nUse conversation history between prompts? (y/n): ").strip().lower() == 'y'

        print()
        results = client.batch_mode(prompts, use_history=use_history)

        # Optionally save results
        save = input("\nSave results to file? (y/n): ").strip().lower()
        if save == 'y':
            filename = input("Enter filename (default: results.json): ").strip() or "results.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Results saved to {filename}")

    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()