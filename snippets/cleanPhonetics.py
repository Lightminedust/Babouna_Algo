import os
import sys
# --- Chemin racine ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from db.connectDb import get_db

db = get_db()

# Table de correspondance
conversion_table = {
    "ɲ": "ny",
    "ʃ": "sh",
    "ʒ": "j",  # pas mentionné explicitement mais souvent converti ainsi
    "ɥ": "yw",
    "ɛ": "ɛ",  # représenté par Ɛ dans ton tableau
    "ø": "eu",  # pas mentionné, on peut ignorer si absent
    "œ": "eu",  # idem
    "ɔ": "ɔ",  # représenté par Ɔ
    "ɛ̃": "ɛ̃",
    "ɔ̃": "ɔ̃",
    "ɑ̃": "ɑ̃",
    "a": "a",
    "b": "b",
    "bv": "bv",
    "dz": "dz",
    "dʒ": "dz",  # variante de dz
    "e": "e",  # mais diphtongue [eɪ] indiquée
    "f": "f",
    "i": "i",
    "ɪi": "ɨ",  # pour Ɨ, rendu par "ɨ" ou "ɪi"
    "k": "k",
    "l": "l",
    "m": "m",
    "mb": "mb",
    "mpf": "mf",
    "mp": "mp",
    "mbv": "mv",
    "n": "n",
    "nd": "nd",
    "ŋg": "ng",
    "ŋk": "nk",
    "nts": "ns",
    "nt": "nt",
    "ndz": "nz",
    "ŋ": "ŋ",
    "o": "o",
    "oʊ": "o",
    "ɔ": "ɔ",
    "p": "p",
    "pf": "pf",
    "ɾ": "r",
    "s": "s",
    "t": "t",
    "ts": "ts",
    "u": "u",
    "ʊu": "ʉ",  # pour Ʉ (ʉ)
    "w": "w",
    "j": "y",
    "ɥ": "yw"
}

langue = "teke"  # à changer selon votre langue

# Fonction pour transformer les mots
def transform_word(word):
    for phonetic, replacement in conversion_table.items():
        word = word.replace(phonetic, replacement)
    return word

# Collection des mots
mots_collection = db[f"mots_{langue}"]
for mot_doc in mots_collection.find():
    mot = mot_doc.get("mot", "")
    if any(phonetic in mot for phonetic in conversion_table):
        phonetic_raw = mot
        phonetic_clean = transform_word(mot)
        mots_collection.update_one(
            {"_id": mot_doc["_id"]},
            {"$set": {"phonetic_raw": phonetic_raw, "phonetic_clean": phonetic_clean, "mot": phonetic_clean}}
        )
        print(f"[MOT OK] {phonetic_raw} → {phonetic_clean}")
    else:
        print(f"[MOT SKIP] {mot} non transformé")

# Collection des phrases
phrases_collection = db[f"phrases_{langue}"]
for phrase_doc in phrases_collection.find():
    source = phrase_doc.get("source", "")
    if any(phonetic in source for phonetic in conversion_table):
        phonetic_raw = source
        mots = source.split()
        mots_transformes = [transform_word(mot) for mot in mots]
        phonetic_clean = ' '.join(mots_transformes)
        phrases_collection.update_one(
            {"_id": phrase_doc["_id"]},
            {"$set": {"phonetic_raw": phonetic_raw, "source": phonetic_clean}}
        )
        print(f"[PHRASE OK] {phonetic_raw} → {phonetic_clean}")
    else:
        print(f"[PHRASE SKIP] {source} non transformée")
