import os
import json
import sys
from pymongo import MongoClient
from bson import ObjectId

# Configuration des chemins et imports comme avant...
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db
from api.Anthropic import call_anthropic_api

db = get_db()
BATCH_SIZE = 100

prompt_ = """
Tu es un assistant qui filtre des données linguistiques.

Règles :
1. Si un élément avec "class": "phrase" a son champ "source" en français ou en anglais → SUPPRIMER.
2. Si un élément avec "class": "mot" a son champ "mot" en français ou en anglais → SUPPRIMER.

3. Retourne uniquement un objet JSON :
   - "mots": liste des _id (string) à supprimer
   - "phrases": liste des _id (string) à supprimer
4. Rien d’autre que ce JSON valide.
"""

def nettoyer_json(texte: str) -> str:
    if not texte:
        return ""
    texte = texte.strip()
    if texte.startswith("```json"):
        texte = texte[len("```json"):].strip()
    if texte.startswith("```"):
        texte = texte[len("```"):].strip()
    if texte.endswith("```"):
        texte = texte[:-3].strip()
    return texte

def supprimer_ids(ids: list, collection: str) -> int:
    if not ids:
        return 0
    object_ids = [ObjectId(i) for i in ids if ObjectId.is_valid(i)]
    if not object_ids:
        return 0
    result = db[collection].delete_many({"_id": {"$in": object_ids}})
    return result.deleted_count

def filtrer_et_supprimer(langue: str):
    print(f"[Python] Nettoyage base pour langue '{langue}' en cours...")

    mots_data = [
        {"_id": str(d["_id"]), "class": "mot", "mot": d.get("mot", "")}
        for d in db[f"mots_{langue}"].find({}, {"_id": 1, "mot": 1})
    ]
    phrases_data = [
        {"_id": str(d["_id"]), "class": "phrase", "source": d.get("source", "")}
        for d in db[f"phrases_{langue}"].find({}, {"_id": 1, "source": 1})
    ]
    all_data = mots_data + phrases_data

    total_mots_suppr = 0
    total_phrases_suppr = 0

    for start in range(0, len(all_data), BATCH_SIZE):
        batch = all_data[start:start + BATCH_SIZE]
        lot_num = start // BATCH_SIZE + 1
        print(f"\n--- Lot {lot_num} ({len(batch)} éléments) ---")

        # Convertir batch en chaîne JSON (format lisible) avant envoi
        batch_str = json.dumps(batch, ensure_ascii=False)

        # Appeler Anthropic API avec texte string
        response_text = call_anthropic_api(prompt_, batch_str)

        # Nettoyer la réponse de l'API
        response_text = nettoyer_json(response_text)

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

    print(f"\n[Python] Résumé : {total_mots_suppr} mots supprimés, {total_phrases_suppr} phrases supprimées.")
