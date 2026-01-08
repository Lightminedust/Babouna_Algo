import os
from ai21 import AI21Client
from dotenv import load_dotenv
load_dotenv()

# Initialisation du client avec la clé API stockée dans les variables d'environnement
client = AI21Client(api_key=os.environ.get("AI21_API_KEY"))

def Ai21(data, rules):
    # Appel à l'API AI21 Maestro
    response = client.beta.maestro.runs.create_and_poll(
        input=data,
        instructions=rules,
        requirements=[
            {
                "name": "Complete extraction",
                "description": "Extract all relevant linguistic data for words and phrases, do not omit any entries present in the text.",
                "is_mandatory": True,
            },
            {
                "name": "Factual accuracy",
                "description": "Do not invent or infer data beyond what is explicitly present in the text; keep translations and annotations accurate.",
                "is_mandatory": True,
            },
            {
                "name": "Consistent output format",
                "description": "Return a valid JSON array with objects strictly following the specified structure (classes 'mot' and 'phrase' with all requested fields).",
                "is_mandatory": True,
            },
            {
                "name": "Handle missing data",
                "description": "If a field cannot be extracted, fill it with 'NA' or an empty list as appropriate.",
                "is_mandatory": False,
            },
        ],
        output_type={"type": "json"},
        budget="low",
    )
    
    print(response) # Pour voir tout ce qu'il y a dedans

    # Essayer d'accéder au texte produit
    output_text = response.result # probablement ça
    print(output_text)
    return response.result
