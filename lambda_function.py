import json
import traceback
import os
from core.parser import HelloAssoParser
from core.logic import EnrollmentLogic
from services.excel_manager import ExcelManager
from services.whatsapp_service import WhatsAppService
from services.outlook_service import OutlookService

# DEV LOCAL : chargement des variables d'environnement
# from dotenv import load_dotenv
# load_dotenv() 

def lambda_handler(event, context):
    try:
        if event.get('headers', {}).get('make-trigger-api-key') != os.environ['MAKE_TRIGGER_API_KEY']:
            return {'statusCode': 403, 'body': 'Mauvaise clé API depuis Make.com'}
    
        # 1. Récupération des données envoyées par Power Automate
        # Si Power Automate envoie le contenu brut dans 'body'
        email_body = event.get('body', "")
        if not email_body:
            return {'statusCode': 400, 'body': 'Corps de l\'email manquant'}

        # 2. Initialisation de l'API Mistral pour le parsing
        mistral_key = os.environ["MISTRAL_API_KEY"]

        # 3. Initialisation du gestionnaire Excel
        creds_json = json.loads(os.environ['GOOGLE_CREDS']) # Alternative sécurisée pour prod

        # DEV LOCAL : chargement des credentials depuis un fichier JSON
        # with open('auto-sub-management-tv-cf8b4c7b9ab7.json', 'r') as f:
        #     creds_json = json.load(f)

        spreadsheet_id = "15OLd9RvqXzllTTzuNCnHvkfjuzjyYpWfo35nvgfZ63A"
        
        excel_mgr = ExcelManager(spreadsheet_id, creds_json)

        # 4. Initialisation du service WhatsApp
        # whatsapp_token = os.environ["WHATSAPP_TOKEN"]
        # phone_number_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
        # whatsapp_service = WhatsAppService(whatsapp_token, phone_number_id)

        # 5. Initialisation du service Outlook
        outlook_service = OutlookService(
            client_id=os.environ["OUTLOOK_CLIENT_ID"],
            client_secret=os.environ["OUTLOOK_CLIENT_SECRET"],
            refresh_token=os.environ["OUTLOOK_REFRESH_TOKEN"]
        )
        
        # 6. Exécution de la logique métier
        parsed_data = HelloAssoParser.parse_email(email_body, mistral_key)
        print(f"DEBUG - Données extraites : {parsed_data}")

        logic = EnrollmentLogic(excel_mgr, outlook_service=outlook_service)
        for item in parsed_data:
            logic.process(item)

        return {
            'statusCode': 200,
            'body': json.dumps([f"Adhésion de {item['first_name']} traitée avec succès." for item in parsed_data])
        }

    except Exception as e:
        print("ERREUR DÉTAILLÉE :")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps(f"Erreur interne : {str(e)}")
        }