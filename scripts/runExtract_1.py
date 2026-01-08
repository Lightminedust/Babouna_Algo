# run_traitement.py
import sys
import os
import argparse
# Ajoute la racine Scripts au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))  # parent de scripts
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.extract_1 import traiter_pdf_et_sauvegarder

if __name__ == "__main__":
    pdf_path = "Scripts/assets/teke_/teke_base.pdf"  # Remplace par le chemin réel
    langue = "teke"  # Ou autre langue si nécessaire
    traiter_pdf_et_sauvegarder(pdf_path, langue)
