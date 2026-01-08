import os
import shutil
import datetime
import subprocess
import sys
import pymongo

# --- Ajout du chemin racine pour l'import ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from dotenv import load_dotenv
import json
load_dotenv()
from db.connectDb import get_db

# --- Initialisation ---
db = get_db()

# ==============================
# CONFIGURATION
# ==============================
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")   # <-- mets le nom de ta base
BACKUP_DIR = "backups"       # dossier où stocker les sauvegardes
KEEP_DAYS = 7                # nombre de jours à garder les sauvegardes

# ==============================
# SCRIPT
# ==============================
def backup_mongodb():
    # Création du dossier principal si n'existe pas
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Nom du dossier avec date et heure
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dump_path = os.path.join(BACKUP_DIR, f"{DB_NAME}_{timestamp}")

    # Commande mongodump
    cmd = [
        "mongodump",
        f"--uri={MONGO_URI.rstrip('/')}/{DB_NAME}",
        f"--out={dump_path}"
    ]

    print(f"[INFO] Sauvegarde en cours vers {dump_path} ...")
    subprocess.run(cmd, check=True)

    # Compression en zip
    zip_path = f"{dump_path}.zip"
    shutil.make_archive(dump_path, 'zip', dump_path)

    # Suppression du dossier non compressé
    shutil.rmtree(dump_path)

    print(f"[OK] Sauvegarde terminée : {zip_path}")

    # Nettoyage des vieilles sauvegardes
    clean_old_backups()

def clean_old_backups():
    now = datetime.datetime.now()
    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(filepath) and filename.endswith(".zip"):
            # Date depuis le nom du fichier
            try:
                date_str = filename.replace(f"{DB_NAME}_", "").replace(".zip", "")
                file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")
                age_days = (now - file_date).days
                if age_days > KEEP_DAYS:
                    os.remove(filepath)
                    print(f"[CLEAN] Suppression ancienne sauvegarde : {filename}")
            except ValueError:
                pass

if __name__ == "__main__":
    backup_mongodb()
