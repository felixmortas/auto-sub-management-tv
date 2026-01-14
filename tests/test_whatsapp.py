import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_whatsapp_message():
    # --- CONFIGURATION ---
    ACCESS_TOKEN = os.environ["WHATSAPP_TOKEN"]
    PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    RECIPIENT_PHONE = "33779806147" # Votre numéro de test
    
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Utilisation du template "hello_world" fourni par défaut par Meta
    payload = {
        "messaging_product": "whatsapp",
        "to": RECIPIENT_PHONE,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": {
                "code": "en_US"
            }
        }
    }

    print(f"🚀 Envoi du message de test à {RECIPIENT_PHONE}...")

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        # Vérification du statut
        if response.status_code == 200:
            print("✅ Succès !")
            print("Réponse de Meta :", response.json())
        else:
            print(f"❌ Échec (Code: {response.status_code})")
            print("Détails de l'erreur :", response.text)
            
    except Exception as e:
        print(f"💥 Une erreur est survenue : {e}")

if __name__ == "__main__":
    test_whatsapp_message()