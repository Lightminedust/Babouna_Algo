import os
import json
import sys
import re
from pymongo import MongoClient
from bson import ObjectId

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db
from api.Anthropic import call_anthropic_api

db = get_db()
BATCH_SIZE = 100

prompt_ = """
Tu es un assistant qui supprime les doublons.

Règles :
1. Mots : même "mot" + même "trad" → garder 1, supprimer les autres.
2. Phrases : même "source" + même "trad" → garder 1, supprimer les autres.
3. Si les concepts, définitions, le sens ou la signification sont les mêmes → supprimer un et garder l'autre.
4. Ne renvoie qu'un JSON strictement valide :
   - "mots": liste des _id à supprimer
   - "phrases": liste des _id à supprimer
"""

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

def supprimer_ids(ids: list, collection: str) -> int:
    if not ids:
        return 0
    object_ids = [ObjectId(i) for i in ids if ObjectId.is_valid(i)]
    if not object_ids:
        return 0
    result = db[collection].delete_many({"_id": {"$in": object_ids}})
    return result.deleted_count

def nettoyer_doublons(langue: str):
    print(f"[Python] Suppression doublons pour '{langue}'...")

    mots_data = [
        {
            "_id": str(d["_id"]),
            "class": "mot",
            "mot": d.get("mot", ""),
            "trad": d.get("trad", "")
        }
        for d in db[f"mots_{langue}"].find({}, {"_id": 1, "mot": 1, "trad": 1})
    ]

    phrases_data = [
        {
            "_id": str(d["_id"]),
            "class": "phrase",
            "source": d.get("source", ""),
            "trad": d.get("trad", "")
        }
        for d in db[f"phrases_{langue}"].find({}, {"_id": 1, "source": 1, "trad": 1})
    ]

    all_data = mots_data + phrases_data

    total_mots_suppr = 0
    total_phrases_suppr = 0

    for start in range(0, len(all_data), BATCH_SIZE):
        batch = all_data[start:start + BATCH_SIZE]
        lot_num = start // BATCH_SIZE + 1

        print(f"\n--- Lot {lot_num} ({len(batch)} éléments) ---")

        # Convertir batch en string JSON avant envoi à l'API Anthropic
        batch_str = json.dumps(batch, ensure_ascii=False)

        response_text = call_anthropic_api(prompt_, batch_str)
        response_text = nettoyer_reponse_json(response_text)

        try:
            to_delete = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"[Anthropic] Lot {lot_num} : JSON invalide, ignoré.")
            continue

        mots_deleted = supprimer_ids(to_delete.get("mots", []), f"mots_{langue}")
        phrases_deleted = supprimer_ids(to_delete.get("phrases", []), f"phrases_{langue}")

        total_mots_suppr += mots_deleted
        total_phrases_suppr += phrases_deleted

        print(f"[Anthropic] Lot {lot_num} : {mots_deleted} mots supprimés, {phrases_deleted} phrases supprimées")

    print(f"\n[Python] Résumé : {total_mots_suppr} mots et {total_phrases_suppr} phrases supprimés.")
