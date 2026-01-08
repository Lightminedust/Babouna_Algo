import sys
import os
import anthropic
import json
from dotenv import load_dotenv

load_dotenv()

# Ajout du chemin racine
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

api_key = os.getenv("ANTHROPIC_KEY")
client = anthropic.Anthropic(api_key=api_key)

chemin_fichier = os.path.join("Json", "AnthropicStream.json")

def call_anthropic_api(prompt, data):
    try:
        stream = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=40000,
            temperature=0.5,
            system=prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": data
                        }
                    ]
                }
            ],
            stream=True
        )

        response_text = ""
        input_tokens = 0
        output_tokens = 0

        for event in stream:
            if event.type == "message_start":
                input_tokens = event.message.usage.input_tokens
            elif event.type == "content_block_delta":
                chunk = event.delta.text
                response_text += chunk
                print(".", end="", flush=True)
            elif event.type == "message_delta":
                output_tokens = event.usage.output_tokens

        print("\n[INFO] Réponse complète reçue")
        print(f"→ Tokens d'entrée : {input_tokens}")
        print(f"→ Tokens de sortie : {output_tokens}")

        return response_text

    except Exception as e:
        print(f"[ERROR] Appel API ou écriture échouée : {e}")
        return None
