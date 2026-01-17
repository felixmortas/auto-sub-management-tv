import os
import json
from core.judge import Judge
from services.excel_manager import ExcelManager

from dotenv import load_dotenv
load_dotenv()  # Charger les variables d'environnement depuis un fichier .env

def run_tests():
    api_key = os.environ["MISTRAL_API_KEY"]

    print("=== DÉBUT DES TESTS DE JUGE LLM ===")
    
    try:
        # 1. Préparation de la liste des membres à envoyer au juge LLM
        # (Ici, on simule une liste de membres pour le test)
        members_names = ["Jean Dupont", "Marie Curie", "Albert Einstein", "Isaac Newton", "Arturo Araùgo"]


        # 2. Appel du juge LLM
        # (Assurez-vous que votre variable d'env MISTRAL_API_KEY est chargée)
        results_true = Judge.check_names("Arturo Araujo", members_names, api_key)
        results_false = Judge.check_names("Charles Darwin", members_names, api_key)

        # 3. Affichage des résultats         
        print(f"Résultat du check positif de similarité des noms : {results_true}")
        print(f"Résultat du check négatif de similarité des noms : {results_false}")

    except Exception as e:
        print(f"❌ Échec du check de similarité des noms : {str(e)}")

if __name__ == "__main__":
    run_tests()