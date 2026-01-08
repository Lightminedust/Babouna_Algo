import faiss
import numpy as np
import os
import json
import sys

# --- Chemin racine ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db
from bson import ObjectId

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
db = get_db()


def serialize_document(doc):
    def convert(value):
        if isinstance(value, ObjectId):
            return str(value)
        elif isinstance(value, list):
            return [convert(item) for item in value]
        elif isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        return value
    doc = {k: v for k, v in doc.items() if k != "embedding"}  # Supprime l'embedding
    return convert(doc)


def save_faiss_index(langue, collection_name):
    coll = db[f"{collection_name}_{langue}"]
    docs = list(coll.find({"embedding": {"$exists": True}}))
    if not docs:
        return

    embeddings = np.array([doc["embedding"] for doc in docs]).astype("float32")
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)

    index_dir = os.path.join("data", langue)
    os.makedirs(index_dir, exist_ok=True)

    faiss.write_index(index, os.path.join(index_dir, f"{collection_name}.index"))

    # Sauvegarde des documents sans embedding
    meta_docs = [serialize_document(doc) for doc in docs]
    with open(os.path.join(index_dir, f"{collection_name}.json"), "w", encoding="utf-8") as f:
        json.dump(meta_docs, f, ensure_ascii=False, indent=2)

for collection_name in ["mots", "phrases", "regles_grammaire"]:
    save_faiss_index("teke", collection_name)
