import os
import sys
import argparse

# Ajoute la racine Scripts au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))  # parent de scripts
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.extract import extraire_et_inserer

def main():
    parser = argparse.ArgumentParser(description="Importer un fichier PDF dans Babouna DB")
    parser.add_argument("--langue", default="teke", help="Teke")
    parser.add_argument("--fichier", default="assets/teke_/dataBase_2.pdf", help="Chemin vers le PDF")
    parser.add_argument("--source", default="teke_database.pdf", help="Nom de la source")

    args = parser.parse_args()

    extraire_et_inserer(args.fichier, args.langue, args.source)

if __name__ == "__main__":
    main()
