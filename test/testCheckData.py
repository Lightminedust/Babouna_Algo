import os
import json
import sys
import re
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db
from api.Anthropic import call_anthropic_api

db = get_db()

def nettoyer_reponse_json(texte: str) -> str:
    if not texte:
        return ""
    texte = texte.strip()
    texte = re.sub(r"^```json\s*", "", texte)
    texte = re.sub(r"^```", "", texte)
    texte = re.sub(r"```$", "", texte)
    last_bracket = texte.rfind("}")
    if last_bracket != -1:
        texte = texte[:last_bracket + 1]
    return texte.strip()


def verifier_confiance_linguistique(documents: list) -> list:
    prompt = f"""
Tu es un expert linguistique qui analyse des données lexicales extraites d'une base MongoDB.

Je te fournis une liste de documents JSON avec les champs :
- _id : identifiant unique
- mot : le mot dans la langue d'origine
- trad : traduction en français
- phonetic_raw : transcription phonétique brute (optionnelle)
- phonetic_clean : transcription phonétique nettoyée (optionnelle)
- exemples : liste d'exemples, chaque exemple est un objet avec :
    - source : phrase de référence dans la langue d'origine
    - trad : traduction de cette phrase en français

Pour chaque document :
- Évalue la cohérence linguistique globale
- Attribue un score de confiance (trust_score) entre 0 et 1

Réponds UNIQUEMENT avec un JSON valide, sans texte avant ou après, au format :
[
  {{"_id": "...", "trust_score": 0.85}},
  {{"_id": "...", "trust_score": 0.15}}
]

Voici les documents à analyser :
{json.dumps(documents, ensure_ascii=False)}
"""
    reponse_brute = call_anthropic_api(prompt, json.dumps(documents, ensure_ascii=False))
    reponse_json_str = nettoyer_reponse_json(reponse_brute)

    reponse_json_str = re.sub(r",\s*\]", "]", reponse_json_str)

    



def test_verifier_confiance_50(langue: str) -> str:
    mots = list(db[f"mots_{langue}"].find().limit(50))
    dossier_process = os.path.join(root_dir, "process")
    os.makedirs(dossier_process, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"trust_scores_test_{langue}_{timestamp}.json"
    filepath = os.path.join(dossier_process, filename)

    batch_prepared = []
    for d in mots:
        d_clean = {
            "_id": str(d["_id"]),
            "mot": d.get("mot", ""),
            "trad": d.get("trad", ""),
            "phonetic_raw": d.get("phonetic_raw", ""),
            "phonetic_clean": d.get("phonetic_clean", ""),
            "exemples": d.get("exemples", []),
        }
        batch_prepared.append(d_clean)

    print(f"[INFO] Traitement test de 50 documents pour la langue '{langue}'")

    try:
        scores = verifier_confiance_linguistique(batch_prepared)
    except Exception as e:
        print(f"[Erreur] lors de l'appel API : {e}")
        return ""

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Sauvegarde test complète dans : {filepath}")
    return filepath

if __name__ == "__main__":
    test_verifier_confiance_50("teke")