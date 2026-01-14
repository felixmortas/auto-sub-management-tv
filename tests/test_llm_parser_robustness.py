import os
import json
from core.parser import HelloAssoParser

from dotenv import load_dotenv
load_dotenv()  # Charger les variables d'environnement depuis un fichier .env

def run_tests():
    # Chemins des fichiers
    test_files = {
        "TXT": "tests/data/email_test.txt",
        "HTML": "tests/data/email_test.html",
        "JSON": "tests/data/email_test.json"
    }

    api_key = os.environ["MISTRAL_API_KEY"]

    print("=== DÉBUT DES TESTS DE ROBUSTESSE PARSER LLM ===")
    
    for format_type, file_path in test_files.items():
        print(f"\n[Test Format {format_type}] en cours...")
        
        try:
            # 1. Lecture du contenu du fichier
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 2. Appel du parser LLM
            # (Assurez-vous que votre variable d'env MISTRAL_API_KEY est chargée)
            result = HelloAssoParser.parse_email(content, api_key)

            # 3. Validation des données critiques
            assert result['first_name'] == "Félix", f"Prénom incorrect pour {format_type}"
            assert result['last_name'].upper() == "MORTAS", f"Nom incorrect pour {format_type}"
            assert result['email'] == "felix.mortas@hotmail.fr", f"Email incorrect pour {format_type}"
            assert result['has_plot'] is True, f"Détection de parcelle échouée pour {format_type}"
            assert result['year'] == "2026", f"Année incorrecte pour {format_type}"
            
            print(f"✅ Succès : Le format {format_type} a été parsé correctement.")
            print(f"   Données extraites : {result['first_name']} {result['last_name']} - {result['membership_type']}")

        except Exception as e:
            print(f"❌ Échec pour le format {format_type} : {str(e)}")

if __name__ == "__main__":
    # Note : Créez le dossier 'tests/data' et placez-y vos fichiers avant de lancer
    run_tests()