import re
import os
import sys
from bson import ObjectId
from pymongo import UpdateOne

# --- Définir le chemin racine du projet ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# --- Connexion à la base MongoDB ---
from db.connectDb import get_db
db = get_db()

# ------------------------------------------------
#  Nettoyage basique du texte (suppression ponctuation)
# ------------------------------------------------
def nettoyer_texte(texte):
    """
    Nettoie une chaîne de texte en :
    - Remplaçant tout caractère non alphabétique (sauf apostrophe) par un espace
    - Transformant en minuscules
    - Supprimant les espaces en trop
    """
    return re.sub(r"[^\w’]+", " ", texte).strip().lower()

# ------------------------------------------------
#  Création de l'index des mots
# ------------------------------------------------
def build_mots_index(langue):
    """
    Récupère tous les mots et leurs variantes pour créer un index rapide.

    Structure retournée :
    {
        "mot_nettoye": document_mot_complet,
        ...
    }
    """
    mots = list(db[f"mots_{langue}"].find({}, {"_id": 1, "mot": 1, "variantes": 1}))
    index_mots = {}

    for mot_doc in mots:
        # Liste de toutes les formes à indexer : mot principal + variantes
        mots_a_indexer = [mot_doc.get("mot", "")] + (mot_doc.get("variantes", []) or [])
        for m in mots_a_indexer:
            m_clean = nettoyer_texte(m)
            if m_clean:
                index_mots[m_clean] = mot_doc  # On garde le doc complet pour lier plus tard
    return index_mots

# ------------------------------------------------
#  Récupération des phrases
# ------------------------------------------------
def build_phrases_list(langue):
    """
    Retourne toutes les phrases avec :
    - _id
    - source (langue d'origine)
    - trad (traduction)
    """
    return list(db[f"phrases_{langue}"].find({}, {"_id": 1, "source": 1, "trad": 1}))

# ------------------------------------------------
#  Liaison mots ↔ phrases
# ------------------------------------------------
def lier_en_memoire(langue):
    """
    Associe chaque mot avec les phrases où il apparaît,
    et chaque phrase avec la liste de mots qu'elle contient.
    """
    print(f"[Python] Liaison mots/phrases pour '{langue}'...")

    # Index des mots pour recherche rapide
    index_mots = build_mots_index(langue)
    # Liste des phrases
    phrases = build_phrases_list(langue)

    updates_phrases = []      # Mises à jour pour les phrases
    exemples_par_mot = {}     # { mot_id: set((source, trad)) }

    for phrase in phrases:
        phrase_id = phrase["_id"]
        source = phrase.get("source", "")
        trad = phrase.get("trad", "")

        # On découpe la phrase en mots
        mots_source = set(nettoyer_texte(source).split())

        mots_trouves = []
        for mot in mots_source:
            if mot in index_mots:
                mot_doc = index_mots[mot]
                mots_trouves.append(mot_doc["mot"])  # Ajout du mot texte

                # On stocke l'exemple pour ce mot
                exemples_par_mot.setdefault(mot_doc["_id"], set()).add((source, trad))

        # Mise à jour de la phrase avec la liste de mots trouvés
        updates_phrases.append(UpdateOne(
            {"_id": phrase_id},
            {"$set": {"mots": mots_trouves}}
        ))

    # Préparation des mises à jour pour chaque mot
    updates_mots = []
    for mot_id, exemples in exemples_par_mot.items():
        exemples_list = [{"source": s, "trad": t} for s, t in exemples]
        updates_mots.append(UpdateOne(
            {"_id": mot_id},
            {"$addToSet": {"exemples": {"$each": exemples_list}}}
        ))

    # Exécution en masse pour optimiser
    if updates_phrases:
        db[f"phrases_{langue}"].bulk_write(updates_phrases)
    if updates_mots:
        db[f"mots_{langue}"].bulk_write(updates_mots)

    print(f"[Python] Liaison terminée pour '{langue}'.")
