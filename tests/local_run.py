import json
import os
from lambda_function import lambda_handler

def simulate_lambda():
    # 1. Charger le contenu du fichier texte
    file_path = 'tests/data/email_test.txt'
    
    if not os.path.exists(file_path):
        print(f"Erreur : Le fichier {file_path} est introuvable.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        email_content = f.read()

    # 2. Simuler l'objet 'event' que Power Automate enverrait à AWS
    # Power Automate envoie généralement le corps du mail dans un champ 'body'
    mock_event = {
        "body": email_content
    }

    print("--- Démarrage de la simulation locale ---")
    
    # 3. Appeler le handler de votre Lambda
    # Le 'None' remplace l'objet 'context' d'AWS qui n'est pas utile ici
    response = lambda_handler(mock_event, None)
    
    print("--- Simulation terminée ---")
    print(f"Réponse de la Lambda : {response}")

if __name__ == "__main__":
    simulate_lambda()