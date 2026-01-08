from sentence_transformers import SentenceTransformer
import os
import sys

# Ajoute le dossier parent au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db

# --- Chargement du modèle ---
model = SentenceTransformer('all-MiniLM-L6-v2')

# Connexion DB
db = get_db()

def search_all(langue, query):
    """
    Recherche vectorielle dans mots, phrases et regles
    avec des top_k différents.
    """
    collections_config = {
        "mots": {"name": f"mots_{langue}", "top_k": 10},
        "phrases": {"name": f"phrases_{langue}", "top_k": 5},
        "regles": {"name": f"regles_grammaire_{langue}", "top_k": 10}
    }

    query_vector = model.encode(query).tolist()
    results_all = {}

    for type_data, cfg in collections_config.items():
        col = db[cfg["name"]]
        pipeline = [
            {
                "$search": {
                    "index": cfg["name"],  # Nom exact de l'index Atlas
                    "knnBeta": {
                        "vector": query_vector,
                        "path": "embedding",
                        "k": cfg["top_k"]
                    }
                }
            },
            {
                "$project": {
                    "score": {"$meta": "searchScore"},
                    "mot": 1,
                    "trad": 1,
                    "source": 1,
                    "description": 1,
                    "exemple": 1
                }
            }
        ]
        results = list(col.aggregate(pipeline))
        results_all[type_data] = results

    return results_all

if __name__ == "__main__":
    langue = "teke"
    query = "papa"

    all_results = search_all(langue, query)

    print("\n=== Résultats 'mots' ===")
    for r in all_results["mots"]:
        print(f"[score: {r['score']:.4f}] {r}")

    print("\n=== Résultats 'phrases' ===")
    for r in all_results["phrases"]:
        print(f"[score: {r['score']:.4f}] {r}")

    print("\n=== Résultats 'regles' ===")
    for r in all_results["regles"]:
        print(f"[score: {r['score']:.4f}] {r}")
