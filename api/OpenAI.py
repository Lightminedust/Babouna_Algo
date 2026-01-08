import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY_OPENAI = os.getenv("OPENAI_API_KEY")
MODEL_OPENAI = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

if not API_KEY_OPENAI:
    raise ValueError("Clé API OpenAI manquante. Mets-la dans la variable d'environnement OPENAI_API_KEY.")

client = OpenAI(api_key=API_KEY_OPENAI)

def call_openai_api(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL_OPENAI,
        messages=[
            {"role": "system", "content": "Tu renvoies toujours un JSON valide sans texte autour."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()
