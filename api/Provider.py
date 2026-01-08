import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Ajout du chemin racine
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
    
from .Mistral import call_mistral_api
from .OpenAI import call_openai_api
from .Anthropic import call_anthropic_api

PROVIDER = os.getenv("PROVIDER")

PROVIDERS = {
    "OpenAi": call_openai_api,
    "Mistral": call_mistral_api,
    "Anthropic": call_anthropic_api
}

def call_ai(prompt):
    if PROVIDER in PROVIDERS:
        print("Provider called...")
        return PROVIDERS[PROVIDER](prompt)
    else:
        raise ValueError("PROVIDER Error")
        
    
