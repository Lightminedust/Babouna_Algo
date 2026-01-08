from sentence_transformers import SentenceTransformer
import os
import sys

# Ajoute le dossier parent au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db

db = get_db()

def vectorize(langue):
    print(f"--- Début de la vectorisation pour la langue : {langue} ---\n")

    collections = {
        "mots": f"mots_{langue}",
        "phrases": f"phrases_{langue}",
        "regles": f"regles_grammaire_{langue}"
    }

    # Chargement du modèle
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Modèle SentenceTransformer chargé avec succès.\n")

    # Parcours des collections
    for type_data, collection_name in collections.items():
        col = db[collection_name]
        print(f"Traitement de la collection : {collection_name}")

        count_processed = 0
        count_skipped = 0

        for doc in col.find({}):
            _id = doc["_id"]
            if "embedding" in doc:
                count_skipped += 1
                continue

            # Définition du texte selon le type
            if type_data == "mots":
                texte = " ".join([doc.get("mot", ""), doc.get("trad", "")]).strip()
            elif type_data == "phrases":
                texte = " ".join([doc.get("source", ""), doc.get("trad", "")]).strip()
            elif type_data == "regles":
                texte = " ".join([doc.get("description", ""), doc.get("exemple", "")]).strip()
            else:
                texte = ""

            if not texte:
                print(f"[{type_data.upper()}] Document {_id} ignoré (texte vide).")
                continue

            # Encodage
            vecteur = model.encode(texte)
            col.update_one({"_id": _id}, {"$set": {"embedding": vecteur.tolist()}})
            count_processed += 1

            if count_processed % 100 == 0:
                print(f"[{type_data.upper()}] {count_processed} documents vectorisés...")

        print(f"[{type_data.upper()}] Terminé : {count_processed} vectorisés, {count_skipped} ignorés.\n")

    print(f"--- Vectorisation terminée pour la langue : {langue} ---")
