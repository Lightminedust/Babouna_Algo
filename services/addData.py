import sys
import os
import datetime

# Ajoute la racine Scripts au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))  # parent de scripts
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db

db = get_db()

def transcrire_phonetique(phonetic_raw: str) -> str:
    if not phonetic_raw:
        return ""

    remplacements = {
        "ɲ": "gn",
        "ʃ": "ch",
        "ŋ": "ng",
        "ʔ": "'",
        "θ": "th",
        "ð": "dh",
        "ɖ": "d",
        "ɟ": "j",
        "ɾ": "r",
        "ɸ": "f",
        "ʈ": "t",
        "ɡ": "g",
        "ɣ": "gh",
    }

    result = phonetic_raw
    for ipa_char, replacement in remplacements.items():
        result = result.replace(ipa_char, replacement)

    # Garder uniquement lettres, chiffres, espace, apostrophe, tiret
    result = ''.join(c for c in result if c.isalnum() or c in [" ", "'", "-"])

    return result


def ajouter_phrase(langue, source, trad, type_phrase="", temps="", phonetic_raw="", phonetic_clean=None, tags=None, source_doc=""):
    if not source.strip():
        print(f"[WARNING] Phrase vide ignorée (langue: {langue})")
        return

    if phonetic_clean is None:
        phonetic_clean = transcrire_phonetique(phonetic_raw)

    data = {
        "class": "phrase",
        "type": type_phrase,
        "temps": temps,
        "source": source,
        "trad": trad,
        "phonetic_raw": phonetic_raw,
        "phonetic_clean": phonetic_clean,
        "tags": tags or [],
        "source_doc": source_doc,
        "date_added": datetime.datetime.now().isoformat()
    }
    db[f"phrases_{langue.lower()}"].insert_one(data)


def ajouter_mot(langue, mot, type_mot, trad, phonetic_raw="", phonetic_clean=None, exemples=None, variantes=None, tags=None, source_doc=""):
    if not mot.strip():
        print(f"[WARNING] Mot vide ignoré (langue: {langue})")
        return

    if phonetic_clean is None:
        phonetic_clean = transcrire_phonetique(phonetic_raw)

    print(f"Insertion mot: {mot} (type: {type_mot}), phonetic_raw: {phonetic_raw}, phonetic_clean: {phonetic_clean}")

    data = {
        "class": "mot",
        "type": type_mot,
        "mot": mot,
        "trad": trad,
        "phonetic_raw": phonetic_raw,
        "phonetic_clean": phonetic_clean,
        "tags": tags or [],
        "exemples": exemples or [],  # ✅ cohérent avec extract.py
        "variantes": variantes or [],
        "source_doc": source_doc,
        "date_added": datetime.datetime.now().isoformat()
    }
    db[f"mots_{langue.lower()}"].insert_one(data)


def ajouter_regle(langue, type_regle, titre, description, exemple, tags=None, source_doc=""):
    if not titre.strip():
        print(f"[WARNING] Règle vide ignorée (langue: {langue})")
        return

    data = {
        "class": "regle",
        "type": type_regle,   # ex: "orthographe", "syntaxe", "morphologie"
        "titre": titre,
        "description": description,
        "exemple": exemple,
        "tags": tags or [],
        "source_doc": source_doc,
        "date_added": datetime.datetime.now().isoformat()
    }
    db[f"regles_grammaire_{langue.lower()}"].insert_one(data)


def ajouter_proverbe(langue, texte, trad, explication="", tags=None, source_doc=""):
    if not texte.strip():
        print(f"[WARNING] Proverbe vide ignoré (langue: {langue})")
        return

    data = {
        "class": "proverbe",
        "type": "proverbe",
        "texte": texte,
        "trad": trad,
        "explication": explication,
        "tags": tags or [],
        "source_doc": source_doc,
        "date_added": datetime.datetime.now().isoformat()
    }
    db[f"proverbes_{langue.lower()}"].insert_one(data)
