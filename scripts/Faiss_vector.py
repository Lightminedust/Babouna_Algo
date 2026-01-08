import os
import sys
import numpy as np
import json
import faiss
from sentence_transformers import SentenceTransformer

# --- Ajout du chemin racine pour l'import ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db

# --- Initialisation ---
db = get_db()
model = SentenceTransformer("all-MiniLM-L6-v2")

def charger_index_depuis_fichier(langue, collection_name):
    index_path = os.path.join("data", langue, f"{collection_name}.index")
    meta_path = os.path.join("data", langue, f"{collection_name}.json")

    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        return [], None

    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    return docs, index

def chercher_similaires(collection_name, docs, index, query_vector, top_k=5):
    distances, indices = index.search(query_vector, top_k)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        doc = docs[idx]
        results.append({
            "collection": collection_name,
            "distance": float(dist),
            "document": doc
        })
    return results


def trouver_par_vectorisation(langue, requete, top_k=5):
    query_vector = model.encode([requete]).astype("float32")
    all_results = []

    # --- Mots ---
    docs_mots, index_mots = charger_index_depuis_fichier(langue, "mots")
    if index_mots:
        all_results += chercher_similaires("mots", docs_mots, index_mots, query_vector, top_k)

    # --- Phrases ---
    docs_phrases, index_phrases = charger_index_depuis_fichier(langue, "phrases")
    if index_phrases:
        all_results += chercher_similaires("phrases", docs_phrases, index_phrases, query_vector, top_k)

    # --- Règles ---
    docs_regles, index_regles = charger_index_depuis_fichier(langue, "regles_grammaire")
    if index_regles:
        all_results += chercher_similaires("regles", docs_regles, index_regles, query_vector, top_k)

    # --- Tri global ---
    all_results.sort(key=lambda x: x["distance"])
    return all_results[:top_k]


# --- Exemple d'utilisation ---
if __name__ == "__main__":
    langue = "teke"
    requete = input("requete: ")
    resultats = trouver_par_vectorisation(langue, requete, top_k=5)

    for i, res in enumerate(resultats, 1):
        doc = res["document"]
        print(f"\n{i}. [Collection: {res['collection']}] - Distance: {res['distance']:.4f}")
        if res["collection"] == "mots":
            print(f"   Mot : {doc.get('mot')} → {doc.get('trad')}")
        elif res["collection"] == "phrases":
            print(f"   Phrase : {doc.get('source')} → {doc.get('trad')}")
        elif res["collection"] == "regles":
            print(f"   Règle : {doc.get('titre')}\n   Desc. : {doc.get('description')}\n   Exemple : {doc.get('exemple')}")
