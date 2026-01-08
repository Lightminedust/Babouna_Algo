import re
import json
import time
import fitz  # PyMuPDF
import sys
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

# Ajout du chemin racine
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.addData import ajouter_phrase, ajouter_mot, ajouter_regle, transcrire_phonetique
from db.connectDb import get_db
from api.Anthropic import call_anthropic_api


db = get_db()

# ===========================
# Lecture et traitement PDF
# ===========================
def lire_pdf_pages(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        return [page.get_text() for page in doc]
    except Exception as e:
        print(f"[ERROR] Lecture PDF : {e}")
        return []

def chunk_pages(pages, taille_chunk=10):
    for i in range(0, len(pages), taille_chunk):
        yield "\n".join(pages[i:i + taille_chunk])

# ===========================
# Nettoyage
# ===========================
def nettoyer_reponse(texte):
    if not texte:
        return ""
    texte = texte.strip()
    texte = re.sub(r"^```json\s*", "", texte, flags=re.IGNORECASE)
    texte = re.sub(r"^```", "", texte)
    texte = re.sub(r"```$", "", texte)
    return texte.strip()

def reparer_json_casse(json_str: str) -> str:
    last_bracket = max(json_str.rfind("]"), json_str.rfind("}"))
    if last_bracket != -1:
        return json_str[:last_bracket + 1]
    return json_str

# ===========================
# Vérification doublons
# ===========================
def element_existe_deja(langue, c, cle_principale, valeur):
    nom_collection = {
        "mot": f"mots_{langue}",
        "phrase": f"phrases_{langue}",
        "regle": f"regles_grammaire_{langue}"
    }.get(c)
    if not nom_collection:
        return False
    return db[nom_collection].find_one({cle_principale: valeur}) is not None

def traduction_meilleure(ancienne, nouvelle):
    if not nouvelle:
        return False
    if not ancienne:
        return True
    return len(nouvelle) > len(ancienne) and nouvelle.lower() != ancienne.lower()

# ===========================
# Prompt principal
# ===========================
def construire_prompt(texte_chunk):
    return f"""
Tu es un linguiste expert. Analyse ce texte dans une langue rare.
traites les données, pour les mots et phrases dans cette langue exotique.
ensuite grace au francais, détermine la traduction, le type, tags, phonetique...
mais les seules données que tu traites sont ceux de cette langue exotique ignore le francais
les symboles ccomme "=" et autres ne font pas partie de cette langue, donc ignore les.
lis le document afin de comprendre le contexte et savoir comment bien traiter les données.
traites toutes les données, n'en oublie pas, fais une verification pour etre sure avant l'envoie

Pour chaque phrase, extrais :
- la phrase originale ("source")
- la traduction complète en français ("trad")
- le type de phrase ("type") et le temps verbal ("temps") si identifiable, sinon ""
- une liste de mots-clés pertinents ("tags")
- enregistre les phrases de manière lisible, sans caractère phonétique

Pour chaque mot présent dans le texte (même s'il n'est pas isolé), extrais :
- le mot ("mot")
- le type grammatical ("type"), par exemple nom, pronom, verbe, adjectif. Essaye toujours de le trouver, sinon mets ""
- sa traduction française ("trad"), déduite uniquement du contexte des phrases où il apparaît. Ne laisse pas ce champ vide si possible.
- les variantes orthographiques ("variantes"), sinon []
- si des mots ont la même traduction ("trad"), choisis-en un et mets les autres dans ses "variantes". Ne crée pas de nouveaux mots.
- dans "exemple", mets les phrases où les mots sont employés et la traduction, le tout séparé par un '/', en string
- enregistre les mots de manière lisible, sans caractère phonétique. Utilise uniquement les caractères de l'alphabet. Ensuite, mets le mot avec la phonétique dans "phonetic_raw" et celui que tu as transformé dans "phonetic_clean" et dans "mot"

Traite aussi les tableaux, retire les informations nécessaires : mot et traduction.
Pour chaque mot ayant la même traduction, n'enregistre qu'un seul mot et mets les autres en variantes.

Réponds UNIQUEMENT avec un tableau JSON valide, sans <think>, sans explication, sans commentaire, sans ```json.

### Exemple de sortie :  
[  
  {{  
    "class": "mot",  
    "type": "verbe",  
    "mot": "ve",  
    "trad": "aller",  
    "phonetic_raw": "",  
    "phonetic_clean": "ve",  
    "tags": ["verbe d'action"],  
    "variantes": [],  
    "exemple": [  
      {{"source": "ma ve wa ngan", "trad": "je vais à la maison"}}  
    ]  
  }},  
  {{  
    "class": "phrase",  
    "type": "déclarative",  
    "temps": "présent",  
    "source": "ma ve wa ngan",  
    "trad": "je vais à la maison",  
    "phonetic_raw": "",  
    "phonetic_clean": "ma ve wa ngan",  
    "tags": ["quotidien", "présent"],  
    "exemple": ""  
  }}
]  

Voici le texte à analyser :  
\"\"\"  
{texte_chunk}  
\"\"\"
"""

prompt_2 = """
Tu es un linguiste expert. Analyse ce texte dans une langue rare.
traites les données, pour les mots et phrases dans cette langue exotique.
ensuite grace au francais, détermine la traduction, le type, tags, phonetique...
mais les seules données que tu traites sont ceux de cette langue exotique ignore le francais
les symboles ccomme "=" et autres ne font pas partie de cette langue, donc ignore les.
lis le document afin de comprendre le contexte et savoir comment bien traiter les données.
traites toutes les données, n'en oublie pas, fais une verification pour etre sure avant l'envoie

Pour chaque phrase, extrais :
- la phrase originale ("source")
- la traduction complète en français ("trad")
- le type de phrase ("type") et le temps verbal ("temps") si identifiable, sinon ""
- une liste de mots-clés pertinents ("tags")
- enregistre les phrases de manière lisible, sans caractère phonétique

Pour chaque mot présent dans le texte (même s'il n'est pas isolé), extrais :
- le mot ("mot")
- le type grammatical ("type"), par exemple nom, pronom, verbe, adjectif. Essaye toujours de le trouver, sinon mets ""
- sa traduction française ("trad"), déduite uniquement du contexte des phrases où il apparaît. Ne laisse pas ce champ vide si possible.
- les variantes orthographiques ("variantes"), sinon []
- si des mots ont la même traduction ("trad"), choisis-en un et mets les autres dans ses "variantes". Ne crée pas de nouveaux mots.
- dans "exemple", mets les phrases où les mots sont employés et la traduction, le tout séparé par un '/', en string
- enregistre les mots de manière lisible, sans caractère phonétique. Utilise uniquement les caractères de l'alphabet. Ensuite, mets le mot avec la phonétique dans "phonetic_raw" et celui que tu as transformé dans "phonetic_clean" et dans "mot"

Pour chaque regles:
- Extrais les règles linguistiques présentes dans ce texte

Traite aussi les tableaux, retire les informations nécessaires : mot et traduction.
Pour chaque mot ayant la même traduction, n'enregistre qu'un seul mot et mets les autres en variantes.

Réponds UNIQUEMENT avec un tableau JSON valide, sans <think>, sans explication, sans commentaire, sans ```json, analyse tout le document, et verifie une seconde fois avant d'envoyer la reponse
Evite les doublons, 
### Exemple de sortie :  
[  
  {
    "class": "mot",  
    "type": "verbe",  
    "mot": "ve",  
    "trad": "aller",  
    "phonetic_raw": "",  
    "phonetic_clean": "ve",  
    "tags": ["verbe d'action"],  
    "variantes": [],  
    "exemple": [  
      {"source": "ma ve wa ngan", "trad": "je vais à la maison"}
    ]  
  },  
  {  
    "class": "phrase",  
    "type": "déclarative",  
    "temps": "présent",  
    "source": "ma ve wa ngan",  
    "trad": "je vais à la maison",  
    "phonetic_raw": "",  
    "phonetic_clean": "ma ve wa ngan",  
    "tags": ["quotidien", "présent"],  
    "exemple": ""  
  },
  {
    "type": "phonétique" | "morphologie" | "syntaxe" | "orthographe" | ...,
    "titre": "Titre explicite et concis de la règle",
    "description": "Description claire et précise de la règle",
    "exemple": "Un ou plusieurs exemples illustratifs",
    "tags": ["liste", "de", "tags", "pertinents"]
  }
]  
"""


# ===========================
# Fonction principale
# ===========================
def extraire_et_inserer(pdf_path, langue, source_doc="Import PDF", taille_chunk=10, pause_sec=2):
    langue = langue.lower()
    pages = lire_pdf_pages(pdf_path)
    if not pages:
        print("[ERROR] Aucune page extraite du PDF.")
        return

    total_chunks = (len(pages) + taille_chunk - 1) // taille_chunk
    print(f"[INFO] Extraction en {total_chunks} chunks de {taille_chunk} pages max chacun.")

    for idx, chunk_text in enumerate(chunk_pages(pages, taille_chunk)):
        print(f"\n--- Début traitement chunk {idx+1}/{total_chunks} ---")
        prompt = construire_prompt(chunk_text)

        try:
            response_text = call_anthropic_api(prompt_2, chunk_text)
            print(response_text)
            if not response_text:
                print(f"[WARNING] Réponse API vide pour chunk {idx+1}")
                continue
        except Exception as e:
            print(f"[ERROR] API Mistral chunk {idx+1} : {e}")
            continue

        json_str = nettoyer_reponse(response_text)

        try:
            donnees = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                donnees = json.loads(reparer_json_casse(json_str))
            except json.JSONDecodeError:
                print(f"[ERROR] JSON invalide chunk {idx+1}")
                continue

        if not isinstance(donnees, list):
            print(f"[WARNING] Résultat inattendu chunk {idx+1} : non liste JSON")
            continue

        uniques = []
        deja_vus = set()
        for item in donnees:
            cle_unique = (item.get("class", "").lower(), item.get("mot", item.get("source", "")).lower())
            if cle_unique not in deja_vus:
                uniques.append(item)
                deja_vus.add(cle_unique)

        nb_insere = 0
        for item in uniques:
            c = item.get("class", "").lower()

            if c == "mot":
                if not element_existe_deja(langue, "mot", "mot", item.get("mot", "")):
                    ajouter_mot(
                        langue,
                        mot=item.get("mot", ""),
                        type_mot=item.get("type", ""),
                        trad=item.get("trad", ""),
                        phonetic_raw=item.get("phonetic_raw", ""),
                        phonetic_clean=item.get("phonetic_clean") or transcrire_phonetique(item.get("phonetic_raw", "")),
                        exemples=item.get("exemple", []),
                        variantes=item.get("variantes", []),
                        source_doc=source_doc
                    )
                    nb_insere += 1
                else:
                    mot_existant = db[f"mots_{langue}"].find_one({"mot": item.get("mot", "")})
                    if mot_existant and traduction_meilleure(mot_existant.get("trad", ""), item.get("trad", "")):
                        db[f"mots_{langue}"].update_one(
                            {"mot": item.get("mot", "")},
                            {"$set": {"trad": item.get("trad", "")}}
                        )

            elif c == "phrase":
                if not element_existe_deja(langue, "phrase", "source", item.get("source", "")):
                    ajouter_phrase(
                        langue,
                        source=item.get("source", ""),
                        trad=item.get("trad", ""),
                        phonetic_raw=item.get("phonetic_raw", ""),
                        phonetic_clean=item.get("phonetic_clean") or transcrire_phonetique(item.get("phonetic_raw", "")),
                        tags=item.get("tags", []),
                        temps=item.get("temps", ""),
                        type_phrase=item.get("type", ""),
                        source_doc=source_doc
                    )
                    nb_insere += 1
            
            elif c == "regle":
                if not element_existe_deja(langue, "regle", "titre", item.get("titre", "")):
                    ajouter_regle(
                        langue=langue,
                        type_regle=item.get("type", "inconnu"),
                        titre=item.get("titre", ""),
                        description=item.get("description", ""),
                        exemple=item.get("exemple", ""),
                        tags=item.get("tags", []),
                        source_doc=os.path.basename(pdf_path)
                    )
                    nb_insere += 1
                    print("Regle:", item.get("titre"))

        print(f"[SUCCESS] Chunk {idx+1} → {nb_insere} éléments ajoutés")
        time.sleep(pause_sec)

    print(f"\n[INFO] Import terminé pour la langue '{langue}'")


def extraire_chunk_unique(pdf_path, langue="teke", taille_lot=5):
    """
    Retraite un ou plusieurs chunks spécifiques (ex: 5 ou 2,4,7)
    et sauvegarde les résultats directement en base de données,
    sans export local.
    """
    langue = langue.lower()
    pages = lire_pdf_pages(pdf_path)
    total_chunks = (len(pages) + taille_lot - 1) // taille_lot

    print(f"[INFO] Le document contient {len(pages)} pages, soit {total_chunks} chunks de {taille_lot} pages.")

    chunks_input = input(">>> Entrez les numéros de chunks à retraiter (ex: 2 ou 3,5,7) : ")
    try:
        chunks_selectionnes = sorted(set(
            int(c.strip()) for c in chunks_input.split(",") if c.strip().isdigit()
        ))
    except Exception:
        print("[ERREUR] Format invalide. Entrez des numéros séparés par des virgules (ex: 1,3,5).")
        return

    for chunk_num in chunks_selectionnes:
        if not (1 <= chunk_num <= total_chunks):
            print(f"[ERREUR] Chunk {chunk_num} est hors limites. Ignoré.")
            continue

        chunk_index = chunk_num - 1
        chunk_text = "\n".join(pages[chunk_index * taille_lot : (chunk_index + 1) * taille_lot])

        print(f"\n[INFO] Appel Claude pour le chunk {chunk_num}...")
        try:
            # Utilise les règles définies dans rulesForAi21
            reponse = call_anthropic_api(prompt_2, chunk_text)
            print(reponse)
        except Exception as e:
            print(f"[ERREUR] Échec appel API pour chunk {chunk_num} : {e}")
            continue
        
        json_str = nettoyer_reponse(reponse)

        try:
            donnees = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                donnees = json.loads(reparer_json_casse(json_str))  # si tu as cette fonction pour tenter de réparer
            except json.JSONDecodeError:
                print(f"[ERREUR] JSON invalide pour chunk {chunk_num}")
                continue

        if not isinstance(donnees, list):
            print(f"[WARNING] Résultat inattendu (non-liste) pour chunk {chunk_num}")
            continue

        uniques = []
        deja_vus = set()
        for item in donnees:
            cle_unique = (item.get("class", "").lower(), item.get("mot", item.get("source", "")).lower())
            if cle_unique not in deja_vus:
                uniques.append(item)
                deja_vus.add(cle_unique)

        nb_insere = 0
        for item in uniques:
            c = item.get("class", "").lower()

            if c == "mot":
                if not element_existe_deja(langue, "mot", "mot", item.get("mot", "")):
                    ajouter_mot(
                        langue,
                        mot=item.get("mot", ""),
                        type_mot=item.get("type", ""),
                        trad=item.get("trad", ""),
                        phonetic_raw=item.get("phonetic_raw", ""),
                        phonetic_clean=item.get("phonetic_clean") or transcrire_phonetique(item.get("phonetic_raw", "")),
                        exemples=item.get("exemple", []),
                        variantes=item.get("variantes", []),
                        source_doc=os.path.basename(pdf_path)
                    )
                    nb_insere += 1

            elif c == "phrase":
                if not element_existe_deja(langue, "phrase", "source", item.get("source", "")):
                    ajouter_phrase(
                        langue,
                        source=item.get("source", ""),
                        trad=item.get("trad", ""),
                        phonetic_raw=item.get("phonetic_raw", ""),
                        phonetic_clean=item.get("phonetic_clean") or transcrire_phonetique(item.get("phonetic_raw", "")),
                        tags=item.get("tags", []),
                        temps=item.get("temps", ""),
                        type_phrase=item.get("type", ""),
                        source_doc=os.path.basename(pdf_path)
                    )
                    nb_insere += 1

        print(f"[✔] Chunk {chunk_num} → {nb_insere} élément(s) inséré(s) en base.\n")
        time.sleep(3)
        
        
        
        