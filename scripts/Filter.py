import os
import sys
import argparse

# Ajoute la racine Scripts au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))  # parent de scripts
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from snippets.cleanData_1 import filtrer_et_supprimer
from snippets.cleanData_2 import nettoyer_doublons

