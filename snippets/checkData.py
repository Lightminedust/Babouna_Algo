# process/trust_streaming.py
import os
import json
import sys
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from pymongo import UpdateOne
from bson import ObjectId

# ajoute le dossier parent au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db
from api.Anthropic import call_anthropic_api  # ta wrapper: call_anthropic_api(prompt, data)

db = get_db()


# --------------------------
# utils
# --------------------------
def nettoyer_reponse_json(texte: str) -> str:
    """Enlève blocs ```json ``` et trim."""
    if not texte:
        return ""
    texte = texte.strip()
    texte = re.sub(r"^```json\s*", "", texte)
    texte = re.sub(r"^```", "", texte)
    texte = re.sub(r"```$", "", texte)
    # Pas de tronçonnage agressif ici : on essaiera d'extraire plus finement si nécessaire
    return texte.strip()


def extract_json_objects_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Tente d'extraire une liste d'objets JSON depuis la réponse texte.
    Approche progressive :
      1) tente json.loads sur le texte complet
      2) si échec, tente d'extraire le sous-texte entre le premier '[' et le dernier ']'
      3) si échec, balaye pour trouver des objets {...} équilibrés et tente de les parser individuellement
    Retourne la liste d'objets valides trouvés (peut être vide).
    """
    objects = []

    if not text:
        return objects

    # nettoyage de base
    t = nettoyer_reponse_json(text)

    # 1) test direct
    try:
        parsed = json.loads(t)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    # 2) tenter d'extraire entre [ ... ]
    s_idx = t.find('[')
    e_idx = t.rfind(']')
    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
        candidate = t[s_idx:e_idx+1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            # continue to fallback
            pass

    # 3) fallback: extraire objets {} par équilibrage d'accolades
    depth = 0
    start = None
    for i, ch in enumerate(t):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    sub = t[start:i+1]
                    # tentative de parse directe
                    try:
                        obj = json.loads(sub)
                        objects.append(obj)
                    except Exception:
                        # tentative de réparation simple : remplacer quotes simples et supprimer trailing commas
                        repaired = sub.replace("'", '"')
                        repaired = re.sub(r",\s*}", "}", repaired)
                        repaired = re.sub(r",\s*\]", "]", repaired)
                        try:
                            obj = json.loads(repaired)
                            objects.append(obj)
                        except Exception:
                            # abandon pour cet objet
                            pass
                    start = None

    return objects


def is_valid_trust(v) -> bool:
    return isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0


# --------------------------
# Fonction principale
# --------------------------
def verifier_confiance_stream(
    langue: str,
    batch_size: int = 100,
    update_db: bool = False,
    limit: Optional[int] = None,
    retries: int = 1,
    sleep_between_retries: float = 1.0,
) -> Dict[str, str]:
    """
    Parcourt la collection mots_{langue} par batch, appelle l'API pour obtenir trust_score,
    écrit en TEMPS RÉEL les résultats (même corrompus) dans un fichier NDJSON dans /process,
    et optionnellement met à jour la DB.

    Retour: dict contenant chemins {'ndjson': ..., 'log': ...}
    """

    coll_name = f"mots_{langue}"
    coll = db[coll_name]

    # Cursor pour ne pas charger toute la collection
    cursor = coll.find({}, {
        "_id": 1, "mot": 1, "trad": 1,
        "phonetic_raw": 1, "phonetic_clean": 1, "exemples": 1
    })
    if limit is not None:
        cursor = cursor.limit(limit)

    # fichiers de sortie
    os.makedirs(os.path.join(root_dir, "process"), exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ndjson_path = os.path.join(root_dir, "process", f"trust_scores_{langue}_{timestamp}.ndjson")
    log_path = os.path.join(root_dir, "process", f"trust_scores_{langue}_{timestamp}.log")

    # ouvrez fichiers en append pour écriture progressive
    f_ndjson = open(ndjson_path, "a", encoding="utf-8")
    f_log = open(log_path, "a", encoding="utf-8")

    def log(msg: str):
        ts = datetime.now().isoformat()
        line = f"{ts} {msg}"
        print(line)
        f_log.write(line + "\n")
        f_log.flush()

    # buffer pour construire le batch
    batch_docs = []
    batch_count = 0
    total_processed = 0

    def flush_batch(batch_list: List[Dict[str, Any]], batch_idx: int):
        nonlocal total_processed
        if not batch_list:
            return

        # Préparer payload (on envoie les docs en JSON)
        data_for_api = json.dumps(batch_list, ensure_ascii=False)
        # Prompt clair (on peut raccourcir les exemples pour ne pas dépasser tokens)
        prompt = f"""
Tu es un expert linguistique qui analyse des données lexicales extraites d'une base MongoDB.
Pour chaque document fourni dans 'data' renvoie un objet avec les champs:
- _id (tel qu'envoyé)
- trust_score : nombre entre 0.0 et 1.0

Réponds uniquement avec un JSON Array d'objets :
[ {{ "_id": "...", "trust_score": 0.85 }} , ... ] 
Rien d'autre.
"""

        # appel API avec retries
        response_text = None
        for attempt in range(0, retries + 1):
            try:
                log(f"[LOT {batch_idx}] Envoi à l'API (tentative {attempt+1}) - {len(batch_list)} docs")
                response_text = call_anthropic_api(prompt, data_for_api)
                log(f"[LOT {batch_idx}] Réponse reçue (longueur {len(response_text)})")
                break
            except Exception as e:
                log(f"[LOT {batch_idx}] Erreur API (tentative {attempt+1}): {e}")
                if attempt < retries:
                    time.sleep(sleep_between_retries)
                else:
                    response_text = None

        if response_text is None:
            # impossible d'obtenir réponse
            log(f"[LOT {batch_idx}] ERREUR FINALE : pas de réponse de l'API pour ce lot.")
            # écrire pour chaque id une entrée corrompue pour ne rien perdre
            for d in batch_list:
                entry = {
                    "_id": d["_id"],
                    "trust_score": None,
                    "error": "no_api_response",
                    "ai_raw": None
                }
                f_ndjson.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f_ndjson.flush()
            return

        # echo response to console and log (truncated to avoid huge logs)
        truncated = response_text if len(response_text) < 4000 else (response_text[:2000] + "\n...[truncated]...\n" + response_text[-1000:])
        log(f"[LOT {batch_idx}] RAW_RESPONSE (truncated):\n{truncated}")

        # tenter d'extraire objets JSON
        parsed_objs = extract_json_objects_from_text(response_text)

        if parsed_objs:
            # crée mapping id -> obj
            parsed_by_id = {}
            for obj in parsed_objs:
                if isinstance(obj, dict) and "_id" in obj:
                    parsed_by_id[str(obj["_id"])] = obj

            # écrire et optionnellement update DB pour chaque doc initial du batch
            updates = []
            for d in batch_list:
                doc_id = str(d["_id"])
                if doc_id in parsed_by_id:
                    obj = parsed_by_id[doc_id]
                    trust = obj.get("trust_score") if "trust_score" in obj else obj.get("trust")
                    # normaliser
                    trust_val = None
                    if is_valid_trust(trust):
                        trust_val = float(trust)
                    else:
                        # si IA a renvoyé quelque chose d'étrange, on marque None
                        trust_val = None

                    entry = {
                        "_id": doc_id,
                        "trust_score": trust_val,
                        "ai_ok": True
                    }
                    # ajouter métadonnées éventuelles
                    if not is_valid_trust(trust):
                        entry["note"] = "invalid_trust_value_from_ai"
                        entry["ai_raw_value"] = trust

                    f_ndjson.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f_ndjson.flush()

                    if update_db and trust_val is not None:
                        try:
                            updates.append(UpdateOne({"_id": ObjectId(doc_id)}, {"$set": {"trust": trust_val}}))
                        except Exception as e:
                            log(f"[LOT {batch_idx}] Impossible créer UpdateOne pour {doc_id}: {e}")
                else:
                    # pas d'objet renvoyé pour ce doc -> écrire ligne corrompue pour ne pas perdre l'id
                    entry = {
                        "_id": doc_id,
                        "trust_score": None,
                        "ai_ok": False,
                        "error": "no_score_for_this_id_in_ai_response",
                        "ai_raw": response_text[:1000]  # on stocke un extrait
                    }
                    f_ndjson.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f_ndjson.flush()

            # écrire aussi les objets renvoyés par l'IA qui ne correspondent pas au batch (surtout utile pour debug)
            for obj in parsed_objs:
                oid = str(obj.get("_id")) if isinstance(obj, dict) and "_id" in obj else None
                if oid and oid not in {str(d["_id"]) for d in batch_list}:
                    # entrée "orphan" venant de l'IA
                    entry = {
                        "_id": oid,
                        "trust_score": obj.get("trust_score", obj.get("trust")),
                        "ai_ok": True,
                        "note": "orphan_from_ai"  # pas dans le batch original
                    }
                    f_ndjson.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f_ndjson.flush()

            # applique bulk write si demandé
            if update_db and updates:
                try:
                    res = db[coll_name].bulk_write(updates)
                    log(f"[LOT {batch_idx}] BulkWrite OK: modified_count={getattr(res, 'modified_count', 'n/a')}")
                except Exception as e:
                    log(f"[LOT {batch_idx}] Erreur BulkWrite: {e}")

        else:
            # impossible de parser quoi que ce soit : on sauvegarde raw response lié à chaque id
            log(f"[LOT {batch_idx}] AUCUN objet JSON extrait : on enregistre les raws par id pour ne rien perdre.")
            for d in batch_list:
                entry = {
                    "_id": d["_id"],
                    "trust_score": None,
                    "ai_ok": False,
                    "error": "could_not_parse_response",
                    "ai_raw": response_text[:2000]
                }
                f_ndjson.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f_ndjson.flush()

        total_processed += len(batch_list)
        log(f"[LOT {batch_idx}] terminé, {len(batch_list)} docs traités (total {total_processed}).")

    # ---------------------------
    # boucle principale sur cursor
    # ---------------------------
    batch_idx = 0
    current_batch = []
    for doc in cursor:
        # normaliser _id en string for sending, but keep original for DB update
        item = {
            "_id": str(doc["_id"]),
            "mot": doc.get("mot", ""),
            "trad": doc.get("trad", ""),
            "phonetic_raw": doc.get("phonetic_raw", ""),
            "phonetic_clean": doc.get("phonetic_clean", ""),
            "exemples": doc.get("exemples", []) or []
        }
        current_batch.append(item)
        if len(current_batch) >= batch_size:
            batch_idx += 1
            try:
                flush_batch(current_batch, batch_idx)
            except Exception as e:
                log(f"[LOT {batch_idx}] Exception inattendue lors flush_batch: {e}")
            current_batch = []

    # flush final
    if current_batch:
        batch_idx += 1
        try:
            flush_batch(current_batch, batch_idx)
        except Exception as e:
            log(f"[LOT {batch_idx}] Exception inattendue lors flush_batch final: {e}")

    log(f"[FIN] Traitement terminé. Fichiers : {ndjson_path} (NDJSON) - {log_path} (log)")

    f_ndjson.close()
    f_log.close()

    return {"ndjson": ndjson_path, "log": log_path}


def appliquer_trust_depuis_ndjson(ndjson_path: str, langue: str, db, batch_size: int = 100):
    """
    Lit un fichier NDJSON contenant {"_id": ..., "trust_score": ...} et met à jour les documents
    dans la collection mots_{langue} avec le champ trust = trust_score.

    Args:
        ndjson_path (str): chemin vers le fichier NDJSON
        langue (str): suffixe de la collection MongoDB, ex "teke"
        db: instance de la base MongoDB
        batch_size (int): taille de batch pour bulk_write
    """
    coll_name = f"mots_{langue}"
    coll = db[coll_name]

    updates = []
    count = 0

    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                doc_id = data.get("_id")
                trust_score = data.get("trust_score")

                # On ne met à jour que si trust_score est valide (float ou int)
                if doc_id and isinstance(trust_score, (int, float)):
                    updates.append(UpdateOne(
                        {"_id": ObjectId(doc_id)},
                        {"$set": {"trust": trust_score}}
                    ))
                    count += 1

                # Exécuter par lots pour limiter la mémoire et accélérer l'écriture
                if len(updates) >= batch_size:
                    coll.bulk_write(updates)
                    updates = []

            except Exception as e:
                print(f"Erreur lecture ligne ou update: {e}")

    # flush final
    if updates:
        coll.bulk_write(updates)

    print(f"Mise à jour terminée. Total documents mis à jour : {count}")


# --------------------------
# mode test rapide
# --------------------------
if __name__ == "__main__":
    # test en limit 50 pour vérifier le déroulé rapidement
    #out = verifier_confiance_stream("teke", batch_size=150, update_db=False, retries=1)
    #print("Sortie :", out)
    ndjson_path = "../process/trust_scores_teke_20250811_200654.ndjson"
    appliquer_trust_depuis_ndjson(ndjson_path, "teke", db)
