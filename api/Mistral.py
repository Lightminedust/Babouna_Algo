import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Ajout du chemin racine
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
    
from mistralai import Mistral

# ===========================
# Initialisation Mistral
# ===========================
API_KEY_MISTRAL = os.getenv("MISTRAL_BABOUNA_API_KEY")
if not API_KEY_MISTRAL:
    raise ValueError("⚠️ Clé API Mistral manquante. Mets-la dans la variable d'environnement MISTRAL_BABOUNA_API_KEY.")

mistral_client = Mistral(api_key=API_KEY_MISTRAL)

# ===========================
# API call
# ===========================
def call_mistral_api(prompt: str) -> str:
    """Appelle l'API Mistral avec le prompt donné et retourne le texte brut."""
    response = mistral_client.chat.complete(
        model="mistral-large-latest",
        messages=[
            {"role": "system", "content": "Tu renvoies toujours un JSON valide sans texte autour."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()