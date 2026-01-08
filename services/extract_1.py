import re
import json
import time
import fitz  # PyMuPDF
import sys
import os
from datetime import datetime

# ===========================
# Ajout du chemin racine
# ===========================
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.addData import ajouter_regle
from db.connectDb import get_db
from api.Anthropic import call_anthropic_api


db = get_db()

# ===========================
# Lecture et traitement PDF
# ===========================
def lire_pdf_pages(pdf_path):
    """Lit toutes les pages d'un fichier PDF et retourne une liste de leur contenu textuel."""
    try:
        doc = fitz.open(pdf_path)
        return [page.get_text() for page in doc]
    except Exception as e:
        print(f"[ERREUR] Impossible de lire le fichier PDF : {e}")
        return []

def chunk_pages(pages, taille_chunk=10):
    """Découpe les pages du PDF en blocs de texte de taille spécifiée."""
    for i in range(0, len(pages), taille_chunk):
        yield "\n".join(pages[i:i + taille_chunk])

def Prompt():
    """Construit un prompt clair et structuré pour l'analyse linguistique."""
    return f"""
Tu es un linguiste expert en langues africaines, notamment la langue téké. Tu vas analyser le texte suivant, qui contient des descriptions grammaticales, phonétiques ou syntaxiques.

Ton objectif est d’extraire les règles linguistiques présentes dans ce texte et de les formater sous forme d’un tableau JSON strictement valide. Aucune explication ne doit entourer le JSON.

Chaque règle doit suivre la structure suivante :

[
  {{
    "type": "phonétique" | "morphologie" | "syntaxe" | "orthographe" | ...,
    "titre": "Titre explicite et concis de la règle",
    "description": "Description claire et précise de la règle",
    "exemple": "Un ou plusieurs exemples illustratifs",
    "tags": ["liste", "de", "tags", "pertinents"]
  }}
]

"""

def nettoyer_reponse_json(reponse):
    # Enlève tout avant premier '[' ou '{' et après dernier ']' ou '}'
    debut = min(reponse.find('['), reponse.find('{'))
    fin = max(reponse.rfind(']'), reponse.rfind('}'))
    if debut == -1 or fin == -1:
        return reponse
    return reponse[debut:fin+1]



def traiter_pdf_et_sauvegarder(pdf_path, langue="teke", taille_lot=5):
    """Traite un PDF en extrayant des règles linguistiques via l'API Mistral,
    les enregistre dans MongoDB et les sauvegarde dans un fichier JSON local."""
    
    dossier_json = os.path.join(root_dir, "Json")
    os.makedirs(dossier_json, exist_ok=True)

    pages = lire_pdf_pages(pdf_path)
    print(f"[INFO] PDF chargé : {len(pages)} pages détectées.")

    toutes_les_regles = []

    for i, chunk in enumerate(chunk_pages(pages, taille_lot)):
        print(f"\n[INFO] Traitement du lot {i+1} (pages {i*taille_lot + 1} à {(i+1)*taille_lot})...")

        reponse = call_anthropic_api(Prompt(), chunk)
        if reponse is None:
            print("[ERREUR] Pas de réponse de l'API")
            continue
        json_str = nettoyer_reponse_json(reponse)
        try:
            regles = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[ERREUR] JSON invalide : {e}")
            print(f"[DEBUG] Chaîne JSON reçue :\n{json_str}")
            continue
        try:
            if not isinstance(regles, list):
                raise ValueError("La réponse de l'API n'est pas un tableau JSON valide.")

            for regle in regles:
                ajouter_regle(
                    langue=langue,
                    type_regle=regle.get("type", "inconnu"),
                    titre=regle.get("titre", ""),
                    description=regle.get("description", ""),
                    exemple=regle.get("exemple", ""),
                    tags=regle.get("tags", []),
                    source_doc=os.path.basename(pdf_path)
                )

            toutes_les_regles.extend(regles)
            print(f"[SUCCÈS] {len(regles)} règle(s) ajoutée(s) à la base de données.")

        except Exception as e:
            print(f"[ERREUR] Échec du traitement du lot {i+1} : {e}")

        time.sleep(3)  # pour éviter de surcharger l'API

    # Sauvegarde locale après traitement complet
    if toutes_les_regles:
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_fichier = f"regles_{langue}_{horodatage}.json"
        chemin_fichier = os.path.join(dossier_json, nom_fichier)

        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(toutes_les_regles, f, ensure_ascii=False, indent=2)

        print(f"[✔] Toutes les règles ont été sauvegardées dans : {chemin_fichier}")
    else:
        print("[INFO] Aucune règle extraite. Aucun fichier créé.")
        