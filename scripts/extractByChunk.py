
# run_traitement.py
import sys
import os
import argparse
# Ajoute la racine Scripts au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))  # parent de scripts
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.extract import extraire_chunk_unique

if __name__ == "__main__":
    pdf_path = "Scripts/assets/teke/teke_database.pdf"  # Remplace par le chemin réel
    langue = "teke"  # Ou autre langue si nécessaire
    extraire_chunk_unique(pdf_path, langue)
