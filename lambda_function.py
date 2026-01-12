import json
import traceback
import os
from core.parser import HelloAssoParser
from core.logic import EnrollmentLogic
from services.excel_manager import ExcelManager
from services.whatsapp_service import WhatsAppService

from dotenv import load_dotenv # test pour le dev local
load_dotenv() # test pour le dev local

def lambda_handler(event, context):
    try:
        # 1. Récupération des données envoyées par Power Automate
        # Si Power Automate envoie le contenu brut dans 'body'
        email_body = event.get('body', "")
        if not email_body:
            return {'statusCode': 400, 'body': 'Corps de l\'email manquant'}

        # 2. Parsing de l'email
        parsed_data = HelloAssoParser.parse_email(email_body)
        print(f"DEBUG - Données extraites : {parsed_data}")

        # 3. Initialisation du gestionnaire Excel
        # On peut stocker le JSON du service account dans une var d'env pour plus de sécurité
        # creds_json = json.loads(os.environ['GOOGLE_CREDS']) # Alternative sécurisée pour prod

        # Alternative locale pour le dev
        creds_path = 'auto-sub-management-tv-cf8b4c7b9ab7.json'
        with open(creds_path, 'r') as f:
            creds_json = json.load(f)

        spreadsheet_id = "15OLd9RvqXzllTTzuNCnHvkfjuzjyYpWfo35nvgfZ63A"
        
        excel_mgr = ExcelManager(spreadsheet_id, creds_json)

        # 4. Initialisation du service WhatsApp
        whatsapp_token = os.environ["WHATSAPP_TOKEN"]
        phone_number_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
        whatsapp_service = WhatsAppService(whatsapp_token, phone_number_id)
        
        # 5. Exécution de la logique métier
        logic = EnrollmentLogic(excel_mgr, whatsapp_service)
        logic.process(parsed_data)

        return {
            'statusCode': 200,
            'body': json.dumps(f"Adhésion de {parsed_data['first_name']} traitée avec succès.")
        }

    except Exception as e:
        print("ERREUR DÉTAILLÉE :")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps(f"Erreur interne : {str(e)}")
        }