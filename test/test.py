
import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Ajout du chemin racine
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from api.Provider import call_ai

def main():
    prompt = "Bonjour, comment ça va ?"
    print(prompt)
    result = call_ai(prompt)
    print(result)

if __name__ == "__main__":
    main()
